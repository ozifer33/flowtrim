from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from .models import Lane
from .privacy import scan_text
from .selector import LANE_WALL_TIME_BUDGET_MS


SCHEMA = "flowtrim-benchmark/v1"
RAW_SHORT_TOKEN_LIMIT = 8
VAULT_READONLY_WALL_TIME_BUDGET_MS = 15_000
ATLAS_CONTEXT_METHOD = "atlas-context-economy"
BASELINE_CODE_METHOD = "baseline-code"
PRIVATE_HOME_PATH_RE = re.compile(r"/Users/[^/\s]+(?:/|$)")
SAFE_PAYLOAD_KEYS = frozenset(
    {
        "command",
        "content_hash",
        "delete_items",
        "duplicate_abstractions",
        "estimated_loc_delta",
        "generated_loc_delta",
        "hash",
        "item",
        "must_keep_violation",
        "post_status_hash",
        "pre_status_hash",
        "rationale",
        "reason",
        "requirement_affected",
        "requirements_preserved",
        "sanitized_snippet",
        "severity",
        "source_ids",
        "test_surface_affected",
        "test_surface_preserved",
        "vault_family",
        "version",
    }
)
REQUIRED_VAULT_FAMILIES = frozenset(
    {
        "short-command",
        "rtk-candidate",
        "packet-routing",
        "index-inventory",
        "source-id-preservation",
        "approval-boundary",
    }
)


class BenchmarkStatus(StrEnum):
    OK = "ok"
    SKIPPED = "skipped"
    FAILED = "failed"
    TIMEOUT = "timeout"
    INSUFFICIENT_EVIDENCE = "insufficient-evidence"
    SELECTED = "selected"


MEASUREMENT_OK_STATUSES = frozenset({BenchmarkStatus.OK, BenchmarkStatus.SELECTED})


class MetricFamily(StrEnum):
    TOKEN_BEARING = "token-bearing"
    CODE_LENS = "code-lens"
    REFUSAL_CORRECTNESS = "refusal-correctness"
    VAULT_SEMANTIC = "vault-semantic"


@dataclass(frozen=True)
class RuntimeChanges:
    installs: bool = False
    hooks: bool = False
    proxy: bool = False
    mcp: bool = False
    config_writes: bool = False
    telemetry: bool = False
    stores_raw_output: bool = False
    unapproved_filesystem_writes: bool = False

    @property
    def is_none(self) -> bool:
        return not any(
            (
                self.installs,
                self.hooks,
                self.proxy,
                self.mcp,
                self.config_writes,
                self.telemetry,
                self.stores_raw_output,
                self.unapproved_filesystem_writes,
            )
        )


@dataclass(frozen=True)
class ToolInfo:
    name: str
    available: bool
    version: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class MethodMeasurement:
    method: str
    status: BenchmarkStatus
    tokens: int
    wall_time_ms: int
    timeout: bool
    repeat_count: int
    guard_passed: bool
    reason: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class PreservationSummary:
    passed: bool
    missing_items: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    lane: Lane
    fixture: str
    metric_family: MetricFamily
    methods: list[MethodMeasurement]
    preservation: PreservationSummary
    runtime_changes: RuntimeChanges
    selected_method: str | None = None
    winner: str | None = None
    counts_as_claim: bool = False
    decision_reason: str | None = None


@dataclass(frozen=True)
class BenchmarkReport:
    schema: str
    profile: str
    runtime_changes: RuntimeChanges
    tools: list[ToolInfo]
    cases: list[BenchmarkCase]
    metric_totals: dict[str, dict[str, int]]
    vault_verdict: str
    upgrade_backlog: list[str]


def evaluate_case(case: BenchmarkCase) -> BenchmarkCase:
    raw = _raw_method(case)
    if raw is None:
        raise ValueError(f"benchmark case {case.case_id} requires a raw method")

    if not _raw_is_valid(raw):
        return _insufficient(case, None, "raw-baseline-unavailable")

    if not case.preservation.passed:
        return _insufficient(case, raw.method, "preservation-failed")

    if not case.runtime_changes.is_none:
        return _insufficient(case, raw.method, "runtime-changed")

    if case.metric_family == MetricFamily.VAULT_SEMANTIC:
        return _evaluate_vault_semantic_case(case, raw)

    if case.lane == Lane.EXACT_EVIDENCE or case.metric_family == MetricFamily.REFUSAL_CORRECTNESS:
        return _select_raw(case, "raw", "correct-refusal", counts_as_claim=False)

    if case.metric_family == MetricFamily.TOKEN_BEARING:
        return _evaluate_token_bearing_case(case, raw)

    if case.metric_family == MetricFamily.CODE_LENS:
        return _evaluate_code_lens_case(case, raw)

    return _insufficient(case, raw.method, "unsupported-metric-family")


def build_report(
    profile: str,
    cases: list[BenchmarkCase],
    tools: list[ToolInfo],
    upgrade_backlog: list[str],
) -> BenchmarkReport:
    evaluated_cases = [evaluate_case(case) for case in cases]
    runtime_changes = _merge_runtime_changes(case.runtime_changes for case in evaluated_cases)
    metric_totals = _metric_totals(evaluated_cases)
    vault_verdict = _vault_verdict(profile, evaluated_cases, runtime_changes)

    return BenchmarkReport(
        schema=SCHEMA,
        profile=profile,
        runtime_changes=runtime_changes,
        tools=tools,
        cases=evaluated_cases,
        metric_totals=metric_totals,
        vault_verdict=vault_verdict,
        upgrade_backlog=upgrade_backlog,
    )


def report_to_json(report: BenchmarkReport) -> str:
    _assert_safe_report_payloads(report)
    return json.dumps(_to_jsonable(report), indent=2, sort_keys=True)


def _evaluate_token_bearing_case(
    case: BenchmarkCase, raw: MethodMeasurement
) -> BenchmarkCase:
    if raw.tokens <= RAW_SHORT_TOKEN_LIMIT:
        return _select_raw(case, raw.method, "raw-short-output", counts_as_claim=False)

    candidates = [
        method
        for method in case.methods
        if method.method != raw.method
        and _method_can_win(method, case)
        and method.tokens < raw.tokens
    ]
    if candidates:
        winner = min(candidates, key=lambda method: (method.tokens, method.wall_time_ms, method.method))
        methods = _mark_selected(case.methods, winner.method)
        return replace(
            case,
            methods=methods,
            selected_method=winner.method,
            winner=winner.method,
            counts_as_claim=True,
            decision_reason="lower-token-safe",
        )

    if _has_smaller_guard_failure(case.methods, raw):
        return _insufficient(case, raw.method, "guard-failed")

    if _has_smaller_timeout(case.methods, raw):
        return _insufficient(case, raw.method, "timeout")

    if _has_smaller_over_budget(case.methods, raw, _wall_time_budget(case)):
        return _insufficient(case, raw.method, "over-wall-time-budget")

    return _select_raw(case, raw.method, "raw-best", counts_as_claim=False)


def _evaluate_code_lens_case(case: BenchmarkCase, raw: MethodMeasurement) -> BenchmarkCase:
    candidates = [
        method
        for method in case.methods
        if method.method not in (raw.method, BASELINE_CODE_METHOD)
        and _method_can_win(method, case)
        and _code_lens_payload_is_safe(method)
    ]
    if not candidates:
        return _insufficient(case, raw.method, "insufficient-code-lens-evidence")

    winner = min(candidates, key=lambda method: (method.wall_time_ms, method.method))
    return replace(
        case,
        methods=_mark_selected(case.methods, winner.method),
        selected_method=winner.method,
        winner=winner.method,
        counts_as_claim=False,
        decision_reason="code-lens-safe",
    )


def _evaluate_vault_semantic_case(
    case: BenchmarkCase, raw: MethodMeasurement
) -> BenchmarkCase:
    if not case.preservation.passed:
        return _insufficient(case, raw.method, "preservation-failed")

    if not case.runtime_changes.is_none:
        return _insufficient(case, raw.method, "runtime-changed")

    atlas = next(
        (
            method
            for method in case.methods
            if method.method == ATLAS_CONTEXT_METHOD and _method_can_win(method, case)
        ),
        None,
    )
    if atlas is None:
        return _insufficient(case, raw.method, "atlas-context-economy-unavailable")

    return replace(
        case,
        methods=_mark_selected(case.methods, atlas.method),
        selected_method=atlas.method,
        winner=atlas.method,
        counts_as_claim=False,
        decision_reason="defer-to-atlas-context-economy",
    )


def _raw_method(case: BenchmarkCase) -> MethodMeasurement | None:
    return next((method for method in case.methods if method.method == "raw"), None)


def _raw_is_valid(raw: MethodMeasurement) -> bool:
    return raw.status in MEASUREMENT_OK_STATUSES and raw.guard_passed and not raw.timeout


def _select_raw(
    case: BenchmarkCase,
    selected_method: str,
    decision_reason: str,
    *,
    counts_as_claim: bool,
) -> BenchmarkCase:
    return replace(
        case,
        methods=_mark_selected(case.methods, selected_method),
        selected_method=selected_method,
        winner=selected_method,
        counts_as_claim=counts_as_claim,
        decision_reason=decision_reason,
    )


def _insufficient(
    case: BenchmarkCase, selected_method: str | None, decision_reason: str
) -> BenchmarkCase:
    return replace(
        case,
        methods=_mark_selected(case.methods, selected_method),
        selected_method=selected_method,
        winner=BenchmarkStatus.INSUFFICIENT_EVIDENCE.value,
        counts_as_claim=False,
        decision_reason=f"insufficient-evidence: {decision_reason}",
    )


def _mark_selected(
    methods: list[MethodMeasurement], selected_method: str | None
) -> list[MethodMeasurement]:
    if selected_method is None:
        return list(methods)

    marked = []
    for method in methods:
        if method.method == selected_method and method.status != BenchmarkStatus.SKIPPED:
            marked.append(replace(method, status=BenchmarkStatus.SELECTED))
        else:
            marked.append(method)
    return marked


def _method_can_win(method: MethodMeasurement, case: BenchmarkCase) -> bool:
    if method.status not in MEASUREMENT_OK_STATUSES:
        return False
    if method.timeout or method.status == BenchmarkStatus.TIMEOUT:
        return False
    if not method.guard_passed:
        return False
    return method.wall_time_ms <= _wall_time_budget(case)


def _wall_time_budget(case: BenchmarkCase) -> int:
    if case.metric_family == MetricFamily.VAULT_SEMANTIC:
        return VAULT_READONLY_WALL_TIME_BUDGET_MS
    return LANE_WALL_TIME_BUDGET_MS[case.lane]


def _has_smaller_guard_failure(
    methods: list[MethodMeasurement], raw: MethodMeasurement
) -> bool:
    return any(
        method.method != raw.method
        and method.status != BenchmarkStatus.SKIPPED
        and method.tokens < raw.tokens
        and not method.guard_passed
        for method in methods
    )


def _has_smaller_timeout(methods: list[MethodMeasurement], raw: MethodMeasurement) -> bool:
    return any(
        method.method != raw.method
        and method.status != BenchmarkStatus.SKIPPED
        and method.tokens < raw.tokens
        and (method.timeout or method.status == BenchmarkStatus.TIMEOUT)
        for method in methods
    )


def _has_smaller_over_budget(
    methods: list[MethodMeasurement], raw: MethodMeasurement, wall_time_budget_ms: int
) -> bool:
    return any(
        method.method != raw.method
        and method.status != BenchmarkStatus.SKIPPED
        and method.tokens < raw.tokens
        and method.wall_time_ms > wall_time_budget_ms
        for method in methods
    )


def _metric_totals(cases: list[BenchmarkCase]) -> dict[str, dict[str, int]]:
    totals = {
        MetricFamily.TOKEN_BEARING.value: {
            "cases": 0,
            "wins": 0,
            "tokens_saved": 0,
            "insufficient_evidence": 0,
            "skipped_methods": 0,
        },
        MetricFamily.CODE_LENS.value: {
            "cases": 0,
            "wins": 0,
            "insufficient_evidence": 0,
            "skipped_methods": 0,
            "generated_loc_delta": 0,
            "delete_items": 0,
            "duplicate_abstractions": 0,
        },
        MetricFamily.REFUSAL_CORRECTNESS.value: {
            "cases": 0,
            "correct_refusals": 0,
            "insufficient_evidence": 0,
            "skipped_methods": 0,
        },
        MetricFamily.VAULT_SEMANTIC.value: {
            "cases": 0,
            "atlas_deferrals": 0,
            "insufficient_evidence": 0,
            "skipped_methods": 0,
        },
    }

    for case in cases:
        family = totals[case.metric_family.value]
        family["cases"] += 1
        family["skipped_methods"] += sum(
            1 for method in case.methods if method.status == BenchmarkStatus.SKIPPED
        )
        if case.winner == BenchmarkStatus.INSUFFICIENT_EVIDENCE.value:
            family["insufficient_evidence"] += 1

        if case.metric_family == MetricFamily.TOKEN_BEARING and case.counts_as_claim:
            raw = _raw_method(case)
            selected = _selected_method(case)
            if raw is not None and selected is not None:
                family["wins"] += 1
                family["tokens_saved"] += max(raw.tokens - selected.tokens, 0)

        if case.metric_family == MetricFamily.CODE_LENS and case.winner not in (
            None,
            BenchmarkStatus.INSUFFICIENT_EVIDENCE.value,
        ):
            family["wins"] += 1
            selected = _selected_method(case)
            if selected is not None:
                family["generated_loc_delta"] += _payload_int(
                    selected, "generated_loc_delta"
                )
                family["delete_items"] += _payload_int(selected, "delete_items")
                family["duplicate_abstractions"] += _payload_int(
                    selected, "duplicate_abstractions"
                )

        if (
            case.metric_family == MetricFamily.REFUSAL_CORRECTNESS
            and case.selected_method == "raw"
            and case.decision_reason == "correct-refusal"
        ):
            family["correct_refusals"] += 1

        if (
            case.metric_family == MetricFamily.VAULT_SEMANTIC
            and case.selected_method == ATLAS_CONTEXT_METHOD
        ):
            family["atlas_deferrals"] += 1

    return totals


def _selected_method(case: BenchmarkCase) -> MethodMeasurement | None:
    return next(
        (method for method in case.methods if method.method == case.selected_method),
        None,
    )


def _payload_int(method: MethodMeasurement, key: str) -> int:
    if not method.payload:
        return 0
    value = method.payload.get(key, 0)
    if key == "delete_items" and isinstance(value, list):
        return len(value)
    return value if isinstance(value, int) else 0


def _code_lens_payload_is_safe(method: MethodMeasurement) -> bool:
    payload = method.payload or {}
    return not _code_lens_payload_has_violation(payload)


def _code_lens_payload_has_violation(payload: Any) -> bool:
    if isinstance(payload, dict):
        if payload.get("must_keep_violation") is True:
            return True
        if payload.get("requirement_affected") not in (None, "none"):
            return True
        if payload.get("test_surface_affected") not in (None, "none"):
            return True
        if payload.get("requirements_preserved") is False:
            return True
        if payload.get("test_surface_preserved") is False:
            return True
        return any(_code_lens_payload_has_violation(value) for value in payload.values())

    if isinstance(payload, list | tuple):
        return any(_code_lens_payload_has_violation(item) for item in payload)

    return False


def _merge_runtime_changes(changes: Any) -> RuntimeChanges:
    changes = list(changes)
    return RuntimeChanges(
        installs=any(change.installs for change in changes),
        hooks=any(change.hooks for change in changes),
        proxy=any(change.proxy for change in changes),
        mcp=any(change.mcp for change in changes),
        config_writes=any(change.config_writes for change in changes),
        telemetry=any(change.telemetry for change in changes),
        stores_raw_output=any(change.stores_raw_output for change in changes),
        unapproved_filesystem_writes=any(
            change.unapproved_filesystem_writes for change in changes
        ),
    )


def _vault_verdict(
    profile: str, cases: list[BenchmarkCase], runtime_changes: RuntimeChanges
) -> str:
    if profile != "aql-vault-readonly":
        return "not-vault"

    vault_cases = [
        case for case in cases if _vault_family(case.fixture) in REQUIRED_VAULT_FAMILIES
    ]
    if not vault_cases:
        return BenchmarkStatus.INSUFFICIENT_EVIDENCE.value
    if not runtime_changes.is_none:
        return "not-vault"
    if any(case.winner == BenchmarkStatus.INSUFFICIENT_EVIDENCE.value for case in vault_cases):
        return BenchmarkStatus.INSUFFICIENT_EVIDENCE.value

    passed_families = {
        _vault_family(case.fixture)
        for case in vault_cases
        if case.winner != BenchmarkStatus.INSUFFICIENT_EVIDENCE.value
    }
    has_vault_token_win = any(
        case.metric_family == MetricFamily.TOKEN_BEARING and case.counts_as_claim
        for case in vault_cases
    )
    has_atlas_semantic_deferral = any(
        case.metric_family == MetricFamily.VAULT_SEMANTIC
        and case.selected_method == ATLAS_CONTEXT_METHOD
        for case in vault_cases
    )
    if (
        REQUIRED_VAULT_FAMILIES.issubset(passed_families)
        and has_vault_token_win
        and has_atlas_semantic_deferral
    ):
        return "vault-safe"
    return "hybrid-only"


def _vault_family(fixture: str) -> str:
    family = Path(fixture).stem
    if family.startswith("aql-"):
        family = family.removeprefix("aql-")
    return family


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return {
            field_name: _to_jsonable(getattr(value, field_name))
            for field_name in value.__dataclass_fields__
        }
    return value


def _assert_safe_report_payloads(report: BenchmarkReport) -> None:
    for case in report.cases:
        for method in case.methods:
            if method.payload is not None:
                _assert_safe_payload(method.payload)


def _assert_safe_payload(payload: Any) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if not isinstance(key, str) or key not in SAFE_PAYLOAD_KEYS:
                raise ValueError(f"unsafe payload key: {key}")
            _assert_safe_payload(value)
        return

    if isinstance(payload, list):
        for item in payload:
            _assert_safe_payload(item)
        return

    if isinstance(payload, tuple):
        for item in payload:
            _assert_safe_payload(item)
        return

    if isinstance(payload, str) and (scan_text(payload) or PRIVATE_HOME_PATH_RE.search(payload)):
        raise ValueError("unsafe payload value")
