from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from .metrics import estimate_tokens
from .models import Lane
from .privacy import scan_text
from .public_corpus import (
    DEFAULT_PUBLIC_CACHE_ROOT,
    DEFAULT_PUBLIC_CORPUS_MANIFEST,
    PUBLIC_OPEN_SOURCE_PROFILE,
    PublicRepoSpec,
    load_public_corpus_manifest,
    public_repo_cache_path,
)
from .selector import LANE_WALL_TIME_BUDGET_MS


SCHEMA = "flowtrim-benchmark/v1"
DEFAULT_FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "fixtures"
DEFAULT_WORK_ROOT = Path.home() / "Documents" / "Work"
RAW_SHORT_TOKEN_LIMIT = 8
VAULT_READONLY_WALL_TIME_BUDGET_MS = 15_000
WORK_CODE_WALL_TIME_BUDGET_MS = 500
ATLAS_CONTEXT_METHOD = "atlas-context-economy"
BASELINE_CODE_METHOD = "baseline-code"
WORK_COMMIT_HISTORY_PROFILE = "work-commit-history-readonly"
PUBLIC_PLAYGROUND_PROFILE = "public-playground-readonly"
DEFAULT_WORK_HISTORY_COMMIT_LIMIT = 6
DEFAULT_WORK_HISTORY_FILES_PER_COMMIT = 4
WORK_CODE_EXTENSIONS = frozenset(
    {
        ".dart",
        ".go",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".php",
        ".py",
        ".rb",
        ".swift",
        ".ts",
        ".tsx",
        ".vue",
    }
)
WORK_HISTORY_CODE_EXTENSIONS = frozenset({".dart", ".js", ".jsx", ".ts", ".tsx", ".vue"})
WORK_HISTORY_CONTROL_EXTENSIONS = frozenset(
    {
        ".g.dart",
        ".freezed.dart",
        ".json",
        ".lock",
        ".pbxproj",
        ".plist",
        ".storyboard",
        ".swiftinterface",
        ".xcconfig",
        ".yaml",
        ".yml",
    }
)
WORK_CODE_SKIP_DIRS = frozenset(
    {
        ".git",
        ".next",
        "build",
        "coverage",
        "DerivedData",
        "dist",
        "node_modules",
        "Pods",
        "vendor",
    }
)
WORK_HISTORY_SKIP_PARTS = frozenset(
    {
        ".git",
        ".next",
        "build",
        "coverage",
        "DerivedData",
        "dist",
        "node_modules",
        "Pods",
        "vendor",
    }
)
WORK_HISTORY_SECRET_MARKERS = (
    "/.env",
    "/credential",
    "/credentials/",
    "/secret",
    "/secret_keys/",
    "/secrets/",
    "/token",
)
SAFE_PAYLOAD_KEYS = frozenset(
    {
        "command",
        "content_hash",
        "delete_items",
        "duplicate_abstractions",
        "error_labels",
        "estimated_loc_delta",
        "failing_tests",
        "generated_loc_delta",
        "hash",
        "item",
        "must_keep",
        "must_keep_violation",
        "omitted_noise_classes",
        "post_status_hash",
        "pre_status_hash",
        "primary_files",
        "rationale",
        "reason",
        "requirement_affected",
        "requirements_preserved",
        "sanitized_snippet",
        "severity",
        "source_ids",
        "status",
        "summary_lines",
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
DEFAULT_UPGRADE_BACKLOG = [
    "Keep CI matrix passing for unit tests, benchmark smoke, skill check, and privacy scan.",
    "Document package entry points and source-checkout fallback commands.",
    "Publish only sanitized synthetic benchmark example reports.",
    "Capture RTK and Headroom versions when available without storing local paths.",
    "Document Ponytail lens as complexity reduction, not direct token compression.",
    "Review license, author metadata, default branch, and public remote checklist.",
]


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


@dataclass(frozen=True)
class WorkHistoryFileStat:
    path: str
    extension: str
    added: int
    deleted: int
    churn: int
    category: str


@dataclass(frozen=True)
class WorkHistoryCommit:
    commit: str
    date: str
    files: tuple[WorkHistoryFileStat, ...]
    total_churn: int
    code_churn: int
    control_churn: int
    bucket: str


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
    text = json.dumps(_to_jsonable(report), indent=2, sort_keys=True)
    _assert_safe_report_text(text)
    return text


def load_fixture(path: str | Path, fixtures_root: str | Path | None = None) -> str:
    fixture_path = Path(path)
    if not fixture_path.is_absolute():
        fixture_path = Path(fixtures_root or DEFAULT_FIXTURES_ROOT) / fixture_path
    return fixture_path.read_text(encoding="utf-8")


def build_synthetic_heavy_suite(
    fixtures_root: str | Path | None = None,
) -> list[BenchmarkCase]:
    root = Path(fixtures_root or DEFAULT_FIXTURES_ROOT)
    noisy_pass = load_fixture("logs/noisy-build-pass.txt", root)
    noisy_fail = load_fixture("logs/noisy-build-fail.txt", root)
    cases = [
        _command_case(
            "command-output/short-empty",
            "logs/short-empty.txt",
            root,
            candidates=[
                _rtk_fixture_candidate("", ""),
                _candidate("flowtrim-selected", Lane.COMMAND_OUTPUT, ""),
            ],
            must_preserve=(),
        ),
        _command_case(
            "command-output/noisy-build-pass",
            "logs/noisy-build-pass.txt",
            root,
            candidates=[
                _rtk_fixture_candidate(
                    noisy_pass,
                    "src/example.py FEATURE_FLAG_DEMO SUMMARY keep: 2 passed, 0 failed",
                    must_preserve=("src/example.py", "FEATURE_FLAG_DEMO", "2 passed"),
                ),
                _native_command_candidate(
                    noisy_pass,
                    must_preserve=("src/example.py", "FEATURE_FLAG_DEMO", "2 passed"),
                ),
            ],
            must_preserve=("src/example.py", "FEATURE_FLAG_DEMO", "2 passed"),
        ),
        _command_case(
            "command-output/noisy-build-fail",
            "logs/noisy-build-fail.txt",
            root,
            candidates=[
                _rtk_fixture_candidate(
                    noisy_fail,
                    "src/worker.py RetryBudgetExceeded src/worker.py::test_retry_policy",
                    must_preserve=(
                        "src/worker.py",
                        "RetryBudgetExceeded",
                        "src/worker.py::test_retry_policy",
                    ),
                ),
                _native_command_candidate(
                    noisy_fail,
                    must_preserve=(
                        "src/worker.py",
                        "RetryBudgetExceeded",
                        "src/worker.py::test_retry_policy",
                    ),
                ),
            ],
            must_preserve=(
                "src/worker.py",
                "RetryBudgetExceeded",
                "src/worker.py::test_retry_policy",
            ),
        ),
        _exact_case(
            "exact-evidence/source-quote",
            "exact/source-quote.txt",
            root,
            must_preserve=("quote-demo-001", "source:demo-quote-001"),
        ),
        _exact_case(
            "exact-evidence/failing-stack-trace",
            "exact/failing-stack-trace.txt",
            root,
            must_preserve=("src/example.py", "DEMO_FAILURE"),
        ),
        _exact_case(
            "exact-evidence/line-level-diff",
            "exact/line-level-diff.txt",
            root,
            must_preserve=("src/example.py:10", "net_amount"),
        ),
        _long_context_case(
            "long-context/tool-trace",
            "context/tool-trace.json",
            root,
            "trace-demo-001 job-demo-17 source:demo-trace-001 src/example.py DEMO_FAILURE",
            must_preserve=("trace-demo-001", "job-demo-17", "source:demo-trace-001"),
        ),
        _long_context_case(
            "long-context/handoff",
            "context/handoff.md",
            root,
            "REQ-DEMO-001 do not install optional tools tests/test_example.py src/example.py",
            must_preserve=("REQ-DEMO-001", "tests/test_example.py", "src/example.py"),
        ),
        _marker_only_long_context_case(root),
        _code_generation_case(
            "code-generation/over-abstract-helper",
            "code/over-abstract-helper.txt",
            root,
        ),
        _code_generation_case(
            "code-generation/duplicate-conversion-logic",
            "code/duplicate-conversion-logic.txt",
            root,
        ),
        _mutation_missing_path_case(),
        _mutation_slower_candidate_case(),
        _mutation_guard_failure_case(),
    ]
    return cases


def build_aql_vault_readonly_suite(
    fixtures_root: str | Path | None = None,
    aql_root: str | Path | None = None,
) -> list[BenchmarkCase]:
    root = Path(fixtures_root or DEFAULT_FIXTURES_ROOT)
    live_payload, live_runtime = _aql_readonly_audit(aql_root)

    short_case = _command_case(
        "vault/short-command",
        "vault/aql-short-command.txt",
        root,
        candidates=[_rtk_fixture_candidate("", "compressed")],
        must_preserve=(),
    )
    short_case = _with_runtime_and_payload(short_case, live_runtime, live_payload)

    rtk_case = _command_case(
        "vault/rtk-candidate",
        "vault/aql-rtk-candidate.txt",
        root,
        candidates=[
            _rtk_fixture_candidate(
                load_fixture("vault/aql-rtk-candidate.txt", root),
                load_fixture("vault/aql-rtk-candidate.txt", root)
                + "\nRTK helper metadata",
                must_preserve=("source:demo-vault-rtk-001",),
            )
        ],
        must_preserve=("source:demo-vault-rtk-001",),
    )

    semantic_cases = [
        _vault_semantic_case(
            "vault/packet-routing",
            "vault/aql-packet-routing.md",
            root,
            must_preserve=("tools/aql.py packet", "source:demo-vault-packet-001"),
        ),
        _vault_semantic_case(
            "vault/index-inventory",
            "vault/aql-index-inventory.md",
            root,
            must_preserve=("retrieval-index.jsonl", "source:demo-vault-index-001"),
        ),
        _vault_semantic_case(
            "vault/source-id-preservation",
            "vault/aql-source-id-preservation.md",
            root,
            must_preserve=("source:demo-vault-source-001", "wiki/topics/demo-topic.md"),
        ),
        _vault_semantic_case(
            "vault/approval-boundary",
            "vault/aql-approval-boundary.md",
            root,
            must_preserve=("ask before deleting", "source:demo-vault-approval-001"),
        ),
    ]
    return [short_case, rtk_case, *semantic_cases]


def run_suite(
    profile: str,
    fixtures_root: str | Path | None = None,
    *,
    aql_root: str | Path | None = None,
    work_root: str | Path | None = None,
    work_repos: list[str | Path] | tuple[str | Path, ...] | None = None,
    public_corpus_manifest: str | Path | None = None,
    public_cache_root: str | Path | None = None,
    repo_limit: int = 9,
    files_per_repo: int = 12,
    commit_limit: int = DEFAULT_WORK_HISTORY_COMMIT_LIMIT,
    files_per_commit: int = DEFAULT_WORK_HISTORY_FILES_PER_COMMIT,
    headroom_executable: str | None = None,
) -> BenchmarkReport:
    if profile == "synthetic-heavy":
        cases = build_synthetic_heavy_suite(fixtures_root)
    elif profile == "aql-vault-readonly":
        cases = build_aql_vault_readonly_suite(fixtures_root, aql_root)
    elif profile == "work-code-readonly":
        cases = build_work_code_readonly_suite(
            work_root or DEFAULT_WORK_ROOT,
            repo_limit=repo_limit,
            files_per_repo=files_per_repo,
        )
    elif profile == WORK_COMMIT_HISTORY_PROFILE:
        cases = build_work_commit_history_readonly_suite(
            work_repos or (),
            commit_limit=commit_limit,
            files_per_commit=files_per_commit,
        )
    elif profile == PUBLIC_OPEN_SOURCE_PROFILE:
        cases = build_public_open_source_readonly_suite(
            public_corpus_manifest or DEFAULT_PUBLIC_CORPUS_MANIFEST,
            public_cache_root or DEFAULT_PUBLIC_CACHE_ROOT,
            commit_limit=commit_limit,
            files_per_commit=files_per_commit,
            headroom_executable=headroom_executable,
        )
    elif profile == PUBLIC_PLAYGROUND_PROFILE:
        cases = build_public_playground_readonly_suite()
    else:
        raise ValueError(f"unknown benchmark profile: {profile}")

    return build_report(
        profile,
        cases,
        _tool_infos(),
        list(DEFAULT_UPGRADE_BACKLOG),
    )


def build_public_playground_readonly_suite() -> list[BenchmarkCase]:
    pytest_log = "\n".join(
        [
            "tests/test_public_api.py::test_public_retry FAILED",
            "src/public_api.py:42: PublicRetryError: retry budget exceeded",
            "ERROR keep: src/public_api.py",
            "ERROR keep: PublicRetryError",
            "ERROR keep: tests/test_public_api.py::test_public_retry",
            *[f"INFO noise: pytest progress chunk {index}" for index in range(40)],
        ]
    )
    vite_log = "\n".join(
        [
            "src/App.tsx FEATURE_FLAG_PUBLIC",
            "2 passed, 0 failed",
            *[f"chunk public-{index}.js transformed" for index in range(50)],
        ]
    )
    ts_log = "\n".join(
        [
            "src/types.ts:10:5 - TypeScriptError: Type mismatch",
            "ERROR keep: src/types.ts",
            "ERROR keep: TypeScriptError",
            *[f"INFO noise: tsc diagnostic context {index}" for index in range(35)],
        ]
    )
    diff_text = "\n".join(
        [
            "diff --git a/src/public_api.py b/src/public_api.py",
            "@@ -1,3 +1,3 @@",
            "-old public value",
            "+new public value",
        ]
    )
    duplicate_code = "\n".join(
        [
            "export function publicPlayground(input: string) {",
            "  const repeated = normalizePublicPlaygroundValue(input);",
            "  const repeated = normalizePublicPlaygroundValue(input);",
            "  const repeated = normalizePublicPlaygroundValue(input);",
            "  return repeated;",
            "}",
        ]
    )
    return [
        _inline_command_case(
            "public-playground/pytest-command",
            "public-playground/pytest-log",
            pytest_log,
            must_preserve=(
                "src/public_api.py",
                "PublicRetryError",
                "tests/test_public_api.py::test_public_retry",
            ),
        ),
        _inline_command_case(
            "public-playground/vite-command",
            "public-playground/vite-log",
            vite_log,
            must_preserve=("src/App.tsx", "FEATURE_FLAG_PUBLIC", "2 passed"),
        ),
        _inline_command_case(
            "public-playground/typescript-command",
            "public-playground/typescript-log",
            ts_log,
            must_preserve=("src/types.ts", "TypeScriptError"),
        ),
        _inline_command_case(
            "public-playground/small-command",
            "public-playground/small-command",
            "ok",
            must_preserve=(),
        ),
        _inline_exact_case(
            "public-playground/exact-diff",
            "public-playground/exact-diff",
            diff_text,
            must_preserve=("diff --git", "src/public_api.py"),
        ),
        _inline_code_lens_case(
            "public-playground/code-lens",
            "public-playground/code-lens",
            duplicate_code,
        ),
        _inline_exact_case(
            "public-playground/control-lock",
            "public-playground/control-lock",
            "\n".join(f"package-lock public dependency {index}" for index in range(30)),
            must_preserve=("package-lock",),
        ),
    ]


def build_public_open_source_readonly_suite(
    manifest_path: str | Path,
    cache_root: str | Path,
    *,
    commit_limit: int = DEFAULT_WORK_HISTORY_COMMIT_LIMIT,
    files_per_commit: int = DEFAULT_WORK_HISTORY_FILES_PER_COMMIT,
    headroom_executable: str | None = None,
) -> list[BenchmarkCase]:
    if commit_limit < 1 or files_per_commit < 1:
        return []

    manifest = load_public_corpus_manifest(manifest_path)
    root = Path(cache_root)
    cases: list[BenchmarkCase] = []
    for spec in manifest.repos:
        repo_root = public_repo_cache_path(root, spec)
        if not repo_root.exists():
            raise ValueError(f"public corpus cache missing: {spec.alias}")
        if not _public_commit_exists(repo_root, spec.pinned_commit):
            raise ValueError(f"public corpus pinned commit missing: {spec.alias}")

        repo_label = spec.alias
        pre_status = _run_readonly_git_status(repo_root)
        commits = _select_ranked_history_commits(
            _public_history_commits(repo_root, spec, commit_limit * 4),
            commit_limit,
        )
        post_status = _run_readonly_git_status(repo_root)
        runtime_changes = RuntimeChanges(
            unapproved_filesystem_writes=bool(pre_status) or pre_status != post_status
        )

        commit_number = 1
        for commit in commits:
            commit_label = f"commit-{commit_number:03d}"
            commit_number += 1
            if commit.bucket in ("code-heavy", "command-output-heavy"):
                cases.append(
                    _public_history_command_case(
                        repo_label,
                        commit_label,
                        commit,
                        runtime_changes,
                        headroom_executable=headroom_executable,
                    )
                )
                cases.append(
                    _public_history_exact_case(
                        repo_label,
                        commit_label,
                        commit,
                        runtime_changes,
                    )
                )
                for file_index, stat in enumerate(
                    _select_work_history_code_files(commit, files_per_commit),
                    start=1,
                ):
                    code_case = _public_history_code_case(
                        repo_root,
                        repo_label,
                        commit_label,
                        f"code-{file_index:02d}",
                        commit,
                        stat,
                        runtime_changes,
                    )
                    if code_case is not None:
                        cases.append(code_case)
            elif commit.bucket == "control":
                cases.append(
                    _public_history_control_case(
                        repo_label,
                        commit_label,
                        commit,
                        runtime_changes,
                    )
                )
    return cases


def build_work_commit_history_readonly_suite(
    work_repos: list[str | Path] | tuple[str | Path, ...],
    *,
    commit_limit: int = DEFAULT_WORK_HISTORY_COMMIT_LIMIT,
    files_per_commit: int = DEFAULT_WORK_HISTORY_FILES_PER_COMMIT,
) -> list[BenchmarkCase]:
    if commit_limit < 1 or files_per_commit < 1:
        return []

    cases: list[BenchmarkCase] = []
    for repo_index, repo in enumerate(work_repos, start=1):
        repo_root = Path(repo)
        if not repo_root.exists():
            continue

        repo_label = f"repo-{repo_index:02d}"
        pre_status = _run_readonly_git_status(repo_root)
        commits = _select_work_history_commits(repo_root, commit_limit)
        post_status = _run_readonly_git_status(repo_root)
        runtime_changes = RuntimeChanges(
            unapproved_filesystem_writes=bool(pre_status) or pre_status != post_status
        )

        commit_number = 1
        for commit in commits:
            commit_label = f"commit-{commit_number:03d}"
            commit_number += 1
            if commit.bucket in ("code-heavy", "command-output-heavy"):
                cases.append(
                    _work_history_command_case(repo_label, commit_label, commit, runtime_changes)
                )
                cases.append(
                    _work_history_exact_case(repo_label, commit_label, commit, runtime_changes)
                )
                for file_index, stat in enumerate(
                    _select_work_history_code_files(commit, files_per_commit),
                    start=1,
                ):
                    code_case = _work_history_code_case(
                        repo_root,
                        repo_label,
                        commit_label,
                        f"code-{file_index:02d}",
                        commit,
                        stat,
                        runtime_changes,
                    )
                    if code_case is not None:
                        cases.append(code_case)

            elif commit.bucket == "control":
                cases.append(
                    _work_history_control_case(
                        repo_label,
                        commit_label,
                        commit,
                        runtime_changes,
                    )
                )

    return cases


def build_work_code_readonly_suite(
    work_root: str | Path,
    *,
    repo_limit: int = 9,
    files_per_repo: int = 12,
) -> list[BenchmarkCase]:
    root = Path(work_root)
    if repo_limit < 1 or files_per_repo < 1 or not root.exists():
        return []

    repo_roots = _rank_work_repos(root)[:repo_limit]
    cases: list[BenchmarkCase] = []
    for repo_index, repo_root in enumerate(repo_roots, start=1):
        repo_label = f"repo-{repo_index:02d}"
        pre_status = _run_readonly_git_status(repo_root)
        files = _select_work_code_files(repo_root, files_per_repo)
        post_status = _run_readonly_git_status(repo_root)
        runtime_changes = RuntimeChanges(
            unapproved_filesystem_writes=pre_status != post_status
        )

        for file_index, file_path in enumerate(files, start=1):
            file_label = f"file-{file_index:02d}"
            cases.append(
                _work_code_case(
                    repo_label,
                    file_label,
                    file_path,
                    runtime_changes,
                )
            )
    return cases


def _command_case(
    case_id: str,
    fixture: str,
    fixtures_root: Path,
    *,
    candidates: list[MethodMeasurement],
    must_preserve: tuple[str, ...],
) -> BenchmarkCase:
    from .adapters import RawAdapter

    text = load_fixture(fixture, fixtures_root)
    measured_candidates = _enforce_method_preservation(candidates, must_preserve)
    return BenchmarkCase(
        case_id=case_id,
        lane=Lane.COMMAND_OUTPUT,
        fixture=fixture,
        metric_family=MetricFamily.TOKEN_BEARING,
        methods=[RawAdapter().measure(text, Lane.COMMAND_OUTPUT), *measured_candidates],
        preservation=_preservation_for(text, text, must_preserve),
        runtime_changes=RuntimeChanges(),
    )


def _inline_command_case(
    case_id: str,
    fixture: str,
    text: str,
    *,
    must_preserve: tuple[str, ...],
) -> BenchmarkCase:
    from .adapters import RawAdapter

    candidates = [
        _native_command_candidate(text, must_preserve=must_preserve),
        _candidate(
            "flowtrim-selected",
            Lane.COMMAND_OUTPUT,
            _public_playground_compact_text(text, must_preserve),
            guard_passed=True,
        ),
    ]
    measured_candidates = _enforce_method_preservation(candidates, must_preserve)
    return BenchmarkCase(
        case_id=case_id,
        lane=Lane.COMMAND_OUTPUT,
        fixture=fixture,
        metric_family=MetricFamily.TOKEN_BEARING,
        methods=[RawAdapter().measure(text, Lane.COMMAND_OUTPUT), *measured_candidates],
        preservation=_preservation_for(text, text, must_preserve),
        runtime_changes=RuntimeChanges(),
    )


def _inline_exact_case(
    case_id: str,
    fixture: str,
    text: str,
    *,
    must_preserve: tuple[str, ...],
) -> BenchmarkCase:
    from .adapters import RawAdapter

    return BenchmarkCase(
        case_id=case_id,
        lane=Lane.EXACT_EVIDENCE,
        fixture=fixture,
        metric_family=MetricFamily.REFUSAL_CORRECTNESS,
        methods=[
            RawAdapter().measure(text, Lane.EXACT_EVIDENCE),
            _candidate(
                "unsafe-summary",
                Lane.EXACT_EVIDENCE,
                "public-safe compact exact evidence",
                guard_passed=False,
                reason="exact evidence cannot be summarized",
            ),
        ],
        preservation=_preservation_for(text, text, must_preserve),
        runtime_changes=RuntimeChanges(),
    )


def _inline_code_lens_case(
    case_id: str,
    fixture: str,
    text: str,
) -> BenchmarkCase:
    from .adapters import RawAdapter, hash_text

    raw = RawAdapter().measure(text, Lane.CODE_GENERATION)
    raw = replace(raw, payload={"content_hash": hash_text(text)})
    baseline = replace(raw, method=BASELINE_CODE_METHOD)
    lens = _work_code_lens_measurement(text)
    return BenchmarkCase(
        case_id=case_id,
        lane=Lane.CODE_GENERATION,
        fixture=fixture,
        metric_family=MetricFamily.CODE_LENS,
        methods=[raw, baseline, lens],
        preservation=PreservationSummary(True),
        runtime_changes=RuntimeChanges(),
    )


def _exact_case(
    case_id: str,
    fixture: str,
    fixtures_root: Path,
    *,
    must_preserve: tuple[str, ...],
) -> BenchmarkCase:
    from .adapters import RawAdapter

    text = load_fixture(fixture, fixtures_root)
    return BenchmarkCase(
        case_id=case_id,
        lane=Lane.EXACT_EVIDENCE,
        fixture=fixture,
        metric_family=MetricFamily.REFUSAL_CORRECTNESS,
        methods=[
            RawAdapter().measure(text, Lane.EXACT_EVIDENCE),
            _candidate(
                "unsafe-summary",
                Lane.EXACT_EVIDENCE,
                "compressed exact evidence",
                guard_passed=False,
                reason="exact evidence cannot be summarized",
            ),
        ],
        preservation=_preservation_for(text, text, must_preserve),
        runtime_changes=RuntimeChanges(),
    )


def _long_context_case(
    case_id: str,
    fixture: str,
    fixtures_root: Path,
    compact_text: str,
    *,
    must_preserve: tuple[str, ...],
) -> BenchmarkCase:
    from .adapters import HeadroomAdapter, RawAdapter

    text = load_fixture(fixture, fixtures_root)
    return BenchmarkCase(
        case_id=case_id,
        lane=Lane.LONG_CONTEXT,
        fixture=fixture,
        metric_family=MetricFamily.TOKEN_BEARING,
        methods=[
            RawAdapter().measure(text, Lane.LONG_CONTEXT),
            HeadroomAdapter(which=lambda executable: None).measure(text, Lane.LONG_CONTEXT),
            _candidate(
                "flowtrim-selected",
                Lane.LONG_CONTEXT,
                compact_text,
                guard_passed=all(item in compact_text for item in must_preserve),
            ),
        ],
        preservation=_preservation_for(text, compact_text, must_preserve),
        runtime_changes=RuntimeChanges(),
    )


def _marker_only_long_context_case(fixtures_root: Path) -> BenchmarkCase:
    from .adapters import RawAdapter

    text = load_fixture("context/handoff.md", fixtures_root)
    marker_only = "CCR-MARKER REQ-DEMO-001"
    return BenchmarkCase(
        case_id="long-context/marker-only-unsafe",
        lane=Lane.LONG_CONTEXT,
        fixture="context/handoff.md",
        metric_family=MetricFamily.TOKEN_BEARING,
        methods=[
            RawAdapter().measure(text, Lane.LONG_CONTEXT),
            _candidate(
                "flowtrim-selected",
                Lane.LONG_CONTEXT,
                marker_only,
                guard_passed=False,
                reason="marker-only candidate missing retrieve path",
            ),
        ],
        preservation=PreservationSummary(True),
        runtime_changes=RuntimeChanges(),
    )


def _code_generation_case(
    case_id: str,
    fixture: str,
    fixtures_root: Path,
) -> BenchmarkCase:
    from .adapters import PonytailLens, RawAdapter

    text = load_fixture(fixture, fixtures_root)
    raw = RawAdapter().measure(text, Lane.CODE_GENERATION)
    baseline = replace(raw, method=BASELINE_CODE_METHOD)
    return BenchmarkCase(
        case_id=case_id,
        lane=Lane.CODE_GENERATION,
        fixture=fixture,
        metric_family=MetricFamily.CODE_LENS,
        methods=[raw, baseline, PonytailLens().analyze(text)],
        preservation=PreservationSummary(True),
        runtime_changes=RuntimeChanges(),
    )


def _work_code_case(
    repo_label: str,
    file_label: str,
    file_path: Path,
    runtime_changes: RuntimeChanges,
) -> BenchmarkCase:
    from .adapters import RawAdapter, hash_text

    text = file_path.read_text(encoding="utf-8", errors="ignore")
    raw = RawAdapter().measure(text, Lane.CODE_GENERATION)
    raw = replace(raw, payload={"content_hash": hash_text(text)})
    baseline = replace(raw, method=BASELINE_CODE_METHOD)
    lens = _work_code_lens_measurement(text)
    return BenchmarkCase(
        case_id=f"work-code/{repo_label}/{file_label}",
        lane=Lane.CODE_GENERATION,
        fixture=f"work-code/{repo_label}/{file_label}",
        metric_family=MetricFamily.CODE_LENS,
        methods=[raw, baseline, lens],
        preservation=PreservationSummary(True),
        runtime_changes=runtime_changes,
    )


def _work_code_lens_measurement(text: str) -> MethodMeasurement:
    from .adapters import hash_text

    items = _work_code_delete_items(text)
    payload = {
        "content_hash": hash_text(text),
        "delete_items": items,
        "generated_loc_delta": sum(item["estimated_loc_delta"] for item in items),
        "duplicate_abstractions": sum(
            1 for item in items if "duplicate" in item["rationale"]
        ),
        "requirements_preserved": True,
        "test_surface_preserved": True,
        "must_keep_violation": False,
    }
    has_signal = bool(items)
    return MethodMeasurement(
        method="ponytail-lens",
        status=BenchmarkStatus.OK,
        tokens=estimate_tokens(json.dumps(payload, sort_keys=True)),
        wall_time_ms=0,
        timeout=False,
        repeat_count=1,
        guard_passed=has_signal,
        reason="sanitized static work-code analysis" if has_signal else "no deterministic code reduction signal",
        payload=payload,
    )


def _work_code_delete_items(text: str) -> list[dict[str, Any]]:
    normalized_lines = [_normalize_code_line(line) for line in text.splitlines()]
    meaningful_lines = [line for line in normalized_lines if _meaningful_code_line(line)]
    counts: dict[str, int] = {}
    for line in meaningful_lines:
        counts[line] = counts.get(line, 0) + 1

    items: list[dict[str, Any]] = []
    duplicate_clusters = [
        (line, count)
        for line, count in counts.items()
        if count >= 3 and len(line) >= 18
    ]
    duplicate_clusters.sort(key=lambda item: (-item[1], item[0]))
    for index, (_, count) in enumerate(duplicate_clusters[:3], start=1):
        items.append(
            {
                "item": f"duplicate-code-cluster-{index:02d}",
                "severity": "should-delete",
                "rationale": "duplicate line cluster detected in work code",
                "estimated_loc_delta": -min(count - 1, 12),
                "requirement_affected": "none",
                "test_surface_affected": "none",
                "must_keep_violation": False,
            }
        )

    wrapper_count = sum(1 for line in meaningful_lines if _looks_like_wrapper_line(line))
    if wrapper_count:
        items.append(
            {
                "item": "wrapper-like-forwarding-pattern",
                "severity": "watch",
                "rationale": "wrapper or forwarding pattern detected in work code",
                "estimated_loc_delta": -min(wrapper_count, 8),
                "requirement_affected": "none",
                "test_surface_affected": "none",
                "must_keep_violation": False,
            }
        )

    return items


def _select_work_history_commits(
    repo_root: Path,
    commit_limit: int,
) -> list[WorkHistoryCommit]:
    return _select_ranked_history_commits(_work_history_commits(repo_root), commit_limit)


def _select_ranked_history_commits(
    commits: list[WorkHistoryCommit],
    commit_limit: int,
) -> list[WorkHistoryCommit]:
    code_commits = sorted(
        (commit for commit in commits if commit.bucket == "code-heavy"),
        key=lambda commit: (-commit.code_churn, -len(commit.files), commit.commit),
    )
    command_commits = sorted(
        (commit for commit in commits if commit.bucket == "command-output-heavy"),
        key=lambda commit: (-commit.total_churn, -len(commit.files), commit.commit),
    )
    control_commits = sorted(
        (commit for commit in commits if commit.bucket == "control"),
        key=lambda commit: (-commit.control_churn, -len(commit.files), commit.commit),
    )

    selected: list[WorkHistoryCommit] = []
    seen: set[str] = set()

    def add(commit: WorkHistoryCommit) -> None:
        if len(selected) >= commit_limit or commit.commit in seen:
            return
        selected.append(commit)
        seen.add(commit.commit)

    for commit in code_commits[: max(commit_limit - 1, 1)]:
        add(commit)
    if control_commits:
        add(control_commits[0])
    for commit in command_commits:
        add(commit)
    for commit in code_commits:
        add(commit)

    return selected


def _public_commit_exists(repo_root: Path, pinned_commit: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "cat-file", "-e", f"{pinned_commit}^{{commit}}"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _public_history_commits(
    repo_root: Path,
    spec: PublicRepoSpec,
    max_count: int,
) -> list[WorkHistoryCommit]:
    output = _run_git(
        repo_root,
        [
            "log",
            spec.pinned_commit,
            "--no-merges",
            "--date=short",
            f"--max-count={max_count}",
            "--pretty=format:@@@%H%x09%ad",
            "--numstat",
        ],
        timeout=60,
    )
    commits: list[WorkHistoryCommit] = []
    commit_hash = ""
    date = ""
    files: list[WorkHistoryFileStat] = []

    def flush() -> None:
        if not commit_hash:
            return
        commit = _build_work_history_commit(commit_hash, date, files)
        if commit is not None:
            commits.append(commit)

    for line in output.splitlines():
        if line.startswith("@@@"):
            flush()
            parts = line[3:].split("\t", 1)
            commit_hash = parts[0]
            date = parts[1] if len(parts) > 1 else ""
            files = []
            continue
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        added, deleted, path = parts
        if added == "-" or deleted == "-":
            continue
        try:
            stat = _public_history_file_stat(spec, path, int(added), int(deleted))
        except ValueError:
            continue
        if stat is not None:
            files.append(stat)

    flush()
    return commits


def _public_history_file_stat(
    spec: PublicRepoSpec,
    path: str,
    added: int,
    deleted: int,
) -> WorkHistoryFileStat | None:
    stat = _work_history_file_stat(path, added, deleted)
    if stat is None:
        return None
    if stat.extension in spec.exclude_extensions:
        return replace(stat, category="control")
    if spec.include_extensions and stat.category == "code" and stat.extension not in spec.include_extensions:
        return replace(stat, category="other")
    return stat


def _work_history_commits(repo_root: Path) -> list[WorkHistoryCommit]:
    output = _run_git(
        repo_root,
        [
            "log",
            "--all",
            "--no-merges",
            "--date=short",
            "--pretty=format:@@@%H%x09%ad",
            "--numstat",
        ],
        timeout=60,
    )
    commits: list[WorkHistoryCommit] = []
    commit_hash = ""
    date = ""
    files: list[WorkHistoryFileStat] = []

    def flush() -> None:
        if not commit_hash:
            return
        commit = _build_work_history_commit(commit_hash, date, files)
        if commit is not None:
            commits.append(commit)

    for line in output.splitlines():
        if line.startswith("@@@"):
            flush()
            parts = line[3:].split("\t", 1)
            commit_hash = parts[0]
            date = parts[1] if len(parts) > 1 else ""
            files = []
            continue
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        added, deleted, path = parts
        if added == "-" or deleted == "-":
            continue
        try:
            stat = _work_history_file_stat(path, int(added), int(deleted))
        except ValueError:
            continue
        if stat is not None:
            files.append(stat)

    flush()
    return commits


def _build_work_history_commit(
    commit_hash: str,
    date: str,
    files: list[WorkHistoryFileStat],
) -> WorkHistoryCommit | None:
    if not files:
        return None

    total_churn = sum(stat.churn for stat in files)
    code_churn = sum(stat.churn for stat in files if stat.category == "code")
    control_churn = sum(stat.churn for stat in files if stat.category == "control")
    code_files = sum(1 for stat in files if stat.category == "code")

    if control_churn >= max(30, code_churn * 2):
        bucket = "control"
    elif code_churn >= 12 and code_files >= 2:
        bucket = "code-heavy"
    elif total_churn >= 50 and len(files) >= 4:
        bucket = "command-output-heavy"
    else:
        return None

    return WorkHistoryCommit(
        commit=commit_hash,
        date=date,
        files=tuple(files),
        total_churn=total_churn,
        code_churn=code_churn,
        control_churn=control_churn,
        bucket=bucket,
    )


def _work_history_file_stat(
    path: str,
    added: int,
    deleted: int,
) -> WorkHistoryFileStat | None:
    normalized = path.replace("\\", "/")
    if _work_history_path_is_private_or_ignored(normalized):
        return None

    extension = _work_history_extension(normalized)
    churn = added + deleted
    if extension in WORK_HISTORY_CODE_EXTENSIONS:
        category = "code"
    elif extension in WORK_HISTORY_CONTROL_EXTENSIONS or _work_history_path_is_control(normalized):
        category = "control"
    else:
        category = "other"

    return WorkHistoryFileStat(
        path=normalized,
        extension=extension or "[none]",
        added=added,
        deleted=deleted,
        churn=churn,
        category=category,
    )


def _work_history_path_is_private_or_ignored(path: str) -> bool:
    lowered = "/" + path.lower().strip("/")
    if any(part in WORK_HISTORY_SKIP_PARTS for part in lowered.split("/")):
        return True
    return any(marker in lowered for marker in WORK_HISTORY_SECRET_MARKERS)


def _work_history_path_is_control(path: str) -> bool:
    lowered = "/" + path.lower().strip("/")
    return any(
        marker in lowered
        for marker in (
            "/generated",
            "/ios/",
            "/android/",
            "/build.",
            "/package-lock.",
            "/pubspec.lock",
            "/yarn.lock",
        )
    )


def _work_history_extension(path: str) -> str:
    lowered = path.lower()
    for compound in (".freezed.dart", ".g.dart"):
        if lowered.endswith(compound):
            return compound
    return Path(path).suffix.lower()


def _select_work_history_code_files(
    commit: WorkHistoryCommit,
    limit: int,
) -> list[WorkHistoryFileStat]:
    files = [stat for stat in commit.files if stat.category == "code"]
    files.sort(key=lambda stat: (-stat.churn, stat.extension, stat.path))
    return files[:limit]


def _work_history_command_case(
    repo_label: str,
    commit_label: str,
    commit: WorkHistoryCommit,
    runtime_changes: RuntimeChanges,
) -> BenchmarkCase:
    from .adapters import RawAdapter

    raw_text = _work_history_raw_text(repo_label, commit_label, commit)
    compact = _work_history_compact_text(repo_label, commit_label, commit)
    must_preserve = _work_history_must_preserve(repo_label, commit_label, commit)
    return BenchmarkCase(
        case_id=f"work-history/{repo_label}/{commit_label}/command-01",
        lane=Lane.COMMAND_OUTPUT,
        fixture=f"work-history/{repo_label}/{commit_label}/command-01",
        metric_family=MetricFamily.TOKEN_BEARING,
        methods=[
            RawAdapter().measure(raw_text, Lane.COMMAND_OUTPUT),
            _rtk_fixture_candidate(raw_text, compact, must_preserve=must_preserve),
            _candidate(
                "flowtrim-selected",
                Lane.COMMAND_OUTPUT,
                compact,
                guard_passed=True,
            ),
        ],
        preservation=_preservation_for(raw_text, compact, must_preserve),
        runtime_changes=runtime_changes,
    )


def _public_history_command_case(
    repo_label: str,
    commit_label: str,
    commit: WorkHistoryCommit,
    runtime_changes: RuntimeChanges,
    *,
    headroom_executable: str | None,
) -> BenchmarkCase:
    from .adapters import HeadroomAdapter, RawAdapter

    raw_text = _work_history_raw_text(repo_label, commit_label, commit)
    compact = _work_history_compact_text(repo_label, commit_label, commit)
    must_preserve = _work_history_must_preserve(repo_label, commit_label, commit)
    return BenchmarkCase(
        case_id=f"public-corpus/{repo_label}/{commit_label}/command-01",
        lane=Lane.COMMAND_OUTPUT,
        fixture=f"public-corpus/{repo_label}/{commit_label}/command-01",
        metric_family=MetricFamily.TOKEN_BEARING,
        methods=[
            RawAdapter().measure(raw_text, Lane.COMMAND_OUTPUT),
            _rtk_fixture_candidate(raw_text, compact, must_preserve=must_preserve),
            _native_command_candidate(raw_text, must_preserve=must_preserve),
            HeadroomAdapter(executable=headroom_executable).measure(
                raw_text,
                Lane.COMMAND_OUTPUT,
                must_preserve=must_preserve,
            ),
        ],
        preservation=_preservation_for(raw_text, compact, must_preserve),
        runtime_changes=runtime_changes,
    )


def _work_history_exact_case(
    repo_label: str,
    commit_label: str,
    commit: WorkHistoryCommit,
    runtime_changes: RuntimeChanges,
) -> BenchmarkCase:
    from .adapters import RawAdapter

    raw_text = _work_history_raw_text(repo_label, commit_label, commit)
    return BenchmarkCase(
        case_id=f"work-history/{repo_label}/{commit_label}/exact-01",
        lane=Lane.EXACT_EVIDENCE,
        fixture=f"work-history/{repo_label}/{commit_label}/exact-01",
        metric_family=MetricFamily.REFUSAL_CORRECTNESS,
        methods=[
            RawAdapter().measure(raw_text, Lane.EXACT_EVIDENCE),
            _candidate(
                "unsafe-summary",
                Lane.EXACT_EVIDENCE,
                f"{repo_label} {commit_label} compact private history summary",
                guard_passed=False,
                reason="commit-history exact evidence cannot be summarized",
            ),
        ],
        preservation=_preservation_for(
            raw_text,
            raw_text,
            _work_history_must_preserve(repo_label, commit_label, commit),
        ),
        runtime_changes=runtime_changes,
    )


def _public_history_exact_case(
    repo_label: str,
    commit_label: str,
    commit: WorkHistoryCommit,
    runtime_changes: RuntimeChanges,
) -> BenchmarkCase:
    from .adapters import RawAdapter

    raw_text = _work_history_raw_text(repo_label, commit_label, commit)
    return BenchmarkCase(
        case_id=f"public-corpus/{repo_label}/{commit_label}/exact-01",
        lane=Lane.EXACT_EVIDENCE,
        fixture=f"public-corpus/{repo_label}/{commit_label}/exact-01",
        metric_family=MetricFamily.REFUSAL_CORRECTNESS,
        methods=[
            RawAdapter().measure(raw_text, Lane.EXACT_EVIDENCE),
            _candidate(
                "unsafe-summary",
                Lane.EXACT_EVIDENCE,
                f"{repo_label} {commit_label} compact public history summary",
                guard_passed=False,
                reason="public commit exact evidence cannot be summarized",
            ),
        ],
        preservation=_preservation_for(
            raw_text,
            raw_text,
            _work_history_must_preserve(repo_label, commit_label, commit),
        ),
        runtime_changes=runtime_changes,
    )


def _work_history_code_case(
    repo_root: Path,
    repo_label: str,
    commit_label: str,
    code_label: str,
    commit: WorkHistoryCommit,
    stat: WorkHistoryFileStat,
    runtime_changes: RuntimeChanges,
) -> BenchmarkCase | None:
    from .adapters import RawAdapter

    text = _run_git(repo_root, ["show", f"{commit.commit}:{stat.path}"], timeout=10)
    if not text.strip():
        return None
    raw = RawAdapter().measure(text, Lane.CODE_GENERATION)
    baseline = replace(raw, method=BASELINE_CODE_METHOD)
    return BenchmarkCase(
        case_id=f"work-history/{repo_label}/{commit_label}/{code_label}",
        lane=Lane.CODE_GENERATION,
        fixture=f"work-history/{repo_label}/{commit_label}/{code_label}",
        metric_family=MetricFamily.CODE_LENS,
        methods=[raw, baseline, _work_code_lens_measurement(text)],
        preservation=PreservationSummary(True),
        runtime_changes=runtime_changes,
    )


def _public_history_code_case(
    repo_root: Path,
    repo_label: str,
    commit_label: str,
    code_label: str,
    commit: WorkHistoryCommit,
    stat: WorkHistoryFileStat,
    runtime_changes: RuntimeChanges,
) -> BenchmarkCase | None:
    from .adapters import RawAdapter

    text = _run_git(repo_root, ["show", f"{commit.commit}:{stat.path}"], timeout=10)
    if not text.strip():
        return None
    raw = RawAdapter().measure(text, Lane.CODE_GENERATION)
    baseline = replace(raw, method=BASELINE_CODE_METHOD)
    return BenchmarkCase(
        case_id=f"public-corpus/{repo_label}/{commit_label}/{code_label}",
        lane=Lane.CODE_GENERATION,
        fixture=f"public-corpus/{repo_label}/{commit_label}/{code_label}",
        metric_family=MetricFamily.CODE_LENS,
        methods=[raw, baseline, _work_code_lens_measurement(text)],
        preservation=PreservationSummary(True),
        runtime_changes=runtime_changes,
    )


def _work_history_control_case(
    repo_label: str,
    commit_label: str,
    commit: WorkHistoryCommit,
    runtime_changes: RuntimeChanges,
) -> BenchmarkCase:
    from .adapters import RawAdapter

    raw_text = _work_history_raw_text(repo_label, commit_label, commit)
    return BenchmarkCase(
        case_id=f"work-history/{repo_label}/{commit_label}/control-01",
        lane=Lane.COMMAND_OUTPUT,
        fixture=f"work-history/{repo_label}/{commit_label}/control-01",
        metric_family=MetricFamily.TOKEN_BEARING,
        methods=[RawAdapter().measure(raw_text, Lane.COMMAND_OUTPUT)],
        preservation=PreservationSummary(True),
        runtime_changes=runtime_changes,
    )


def _public_history_control_case(
    repo_label: str,
    commit_label: str,
    commit: WorkHistoryCommit,
    runtime_changes: RuntimeChanges,
) -> BenchmarkCase:
    from .adapters import RawAdapter

    raw_text = _work_history_raw_text(repo_label, commit_label, commit)
    return BenchmarkCase(
        case_id=f"public-corpus/{repo_label}/{commit_label}/control-01",
        lane=Lane.COMMAND_OUTPUT,
        fixture=f"public-corpus/{repo_label}/{commit_label}/control-01",
        metric_family=MetricFamily.TOKEN_BEARING,
        methods=[RawAdapter().measure(raw_text, Lane.COMMAND_OUTPUT)],
        preservation=PreservationSummary(True),
        runtime_changes=runtime_changes,
    )


def _work_history_raw_text(
    repo_label: str,
    commit_label: str,
    commit: WorkHistoryCommit,
) -> str:
    header = _work_history_compact_text(repo_label, commit_label, commit)
    rows = [
        (
            f"{commit_label} file-{index:03d} ext:{stat.extension} "
            f"add:{stat.added} del:{stat.deleted} bucket:{stat.category}"
        )
        for index, stat in enumerate(commit.files, start=1)
    ]
    return "\n".join([header, *rows])


def _work_history_compact_text(
    repo_label: str,
    commit_label: str,
    commit: WorkHistoryCommit,
) -> str:
    return (
        f"{repo_label} {commit_label} bucket:{commit.bucket} "
        f"files:{len(commit.files)} churn:{commit.total_churn} "
        f"code:{commit.code_churn} control:{commit.control_churn} "
        f"top:{_work_history_top_extension(commit)}"
    )


def _work_history_must_preserve(
    repo_label: str,
    commit_label: str,
    commit: WorkHistoryCommit,
) -> tuple[str, ...]:
    return (
        repo_label,
        commit_label,
        f"bucket:{commit.bucket}",
        f"files:{len(commit.files)}",
        f"churn:{commit.total_churn}",
        f"top:{_work_history_top_extension(commit)}",
    )


def _work_history_top_extension(commit: WorkHistoryCommit) -> str:
    churn_by_extension: dict[str, int] = {}
    for stat in commit.files:
        churn_by_extension[stat.extension] = churn_by_extension.get(stat.extension, 0) + stat.churn
    if not churn_by_extension:
        return "[none]"
    return max(churn_by_extension.items(), key=lambda item: (item[1], item[0]))[0]


def _run_git(repo_root: Path, args: list[str], *, timeout: int) -> str:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", *args],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout or ""


def _normalize_code_line(line: str) -> str:
    return " ".join(line.strip().split())


def _meaningful_code_line(line: str) -> bool:
    if len(line) < 12:
        return False
    if not any(character.isalpha() for character in line):
        return False
    stripped = line.strip("{}[]();, ")
    if not stripped:
        return False
    if line.startswith(("//", "#", "*")):
        return False
    return True


def _looks_like_wrapper_line(line: str) -> bool:
    lowered = line.lower()
    return (
        ("=>" in lowered and "(" in lowered and ")" in lowered)
        or lowered.startswith("return await ")
        or ("return " in lowered and lowered.count("(") >= 2)
    )


def _rank_work_repos(work_root: Path) -> list[Path]:
    repos = [git_dir.parent for git_dir in sorted(work_root.glob("*/.git"))]
    return sorted(
        repos,
        key=lambda repo: (_count_code_files(repo), repo.name),
        reverse=True,
    )


def _count_code_files(repo_root: Path) -> int:
    return sum(1 for path in _iter_work_code_files(repo_root))


def _select_work_code_files(repo_root: Path, limit: int) -> list[Path]:
    scored = []
    for path in _iter_work_code_files(repo_root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        score = _work_code_score(text)
        scored.append((score, path.stat().st_size, path.as_posix(), path))
    scored.sort(reverse=True)
    return [path for _, _, _, path in scored[:limit]]


def _iter_work_code_files(repo_root: Path) -> Any:
    for path in repo_root.rglob("*"):
        if any(part in WORK_CODE_SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix not in WORK_CODE_EXTENSIONS:
            continue
        if _looks_like_test_file(path):
            continue
        yield path


def _looks_like_test_file(path: Path) -> bool:
    lowered = path.as_posix().lower()
    return any(
        marker in lowered
        for marker in (
            ".spec.",
            ".test.",
            "__tests__",
            "/test/",
            "/tests/",
        )
    )


def _work_code_score(text: str) -> int:
    items = _work_code_delete_items(text)
    return sum(abs(item["estimated_loc_delta"]) for item in items)


def _vault_semantic_case(
    case_id: str,
    fixture: str,
    fixtures_root: Path,
    *,
    must_preserve: tuple[str, ...],
) -> BenchmarkCase:
    from .adapters import RawAdapter

    text = load_fixture(fixture, fixtures_root)
    atlas_text = " ".join(must_preserve) + " Atlas packet llm_brief source summary"
    return BenchmarkCase(
        case_id=case_id,
        lane=Lane.LONG_CONTEXT,
        fixture=fixture,
        metric_family=MetricFamily.VAULT_SEMANTIC,
        methods=[
            RawAdapter().measure(text, Lane.LONG_CONTEXT),
            _candidate("flowtrim-selected", Lane.LONG_CONTEXT, "compressed vault context"),
            _candidate(
                ATLAS_CONTEXT_METHOD,
                Lane.LONG_CONTEXT,
                atlas_text,
                guard_passed=all(item in atlas_text for item in must_preserve),
            ),
        ],
        preservation=_preservation_for(text, atlas_text, must_preserve),
        runtime_changes=RuntimeChanges(),
    )


def _mutation_missing_path_case() -> BenchmarkCase:
    raw = _candidate("raw", Lane.COMMAND_OUTPUT, "src/example.py TEST_ERROR raw output")
    compact = _candidate("flowtrim-selected", Lane.COMMAND_OUTPUT, "TEST_ERROR compact")
    return BenchmarkCase(
        case_id="mutation/missing-path",
        lane=Lane.COMMAND_OUTPUT,
        fixture="mutation/missing-path",
        metric_family=MetricFamily.TOKEN_BEARING,
        methods=[raw, compact],
        preservation=PreservationSummary(False, ["src/example.py"]),
        runtime_changes=RuntimeChanges(),
    )


def _mutation_slower_candidate_case() -> BenchmarkCase:
    raw = _candidate("raw", Lane.COMMAND_OUTPUT, "raw output " * 80)
    compact = _candidate(
        "flowtrim-selected",
        Lane.COMMAND_OUTPUT,
        "compact",
        wall_time_ms=999,
    )
    return BenchmarkCase(
        case_id="mutation/slower-candidate",
        lane=Lane.COMMAND_OUTPUT,
        fixture="mutation/slower-candidate",
        metric_family=MetricFamily.TOKEN_BEARING,
        methods=[raw, compact],
        preservation=PreservationSummary(True),
        runtime_changes=RuntimeChanges(),
    )


def _mutation_guard_failure_case() -> BenchmarkCase:
    raw = _candidate("raw", Lane.COMMAND_OUTPUT, "src/example.py TEST_ERROR " * 20)
    compact = _candidate(
        "flowtrim-selected",
        Lane.COMMAND_OUTPUT,
        "compact",
        guard_passed=False,
        reason="missing required path",
    )
    return BenchmarkCase(
        case_id="mutation/guard-failure",
        lane=Lane.COMMAND_OUTPUT,
        fixture="mutation/guard-failure",
        metric_family=MetricFamily.TOKEN_BEARING,
        methods=[raw, compact],
        preservation=PreservationSummary(True),
        runtime_changes=RuntimeChanges(),
    )


def _public_playground_compact_text(
    text: str,
    must_preserve: tuple[str, ...],
) -> str:
    if not must_preserve:
        return text
    status = "pass" if "passed" in text.lower() else "fail" if "error" in text.lower() else "ok"
    return " ".join([status, *must_preserve])


def _candidate(
    method: str,
    lane: Lane,
    text: str,
    *,
    status: BenchmarkStatus = BenchmarkStatus.OK,
    wall_time_ms: int = 10,
    timeout: bool = False,
    repeat_count: int = 3,
    guard_passed: bool = True,
    reason: str | None = None,
) -> MethodMeasurement:
    from .adapters import hash_text

    return MethodMeasurement(
        method=method,
        status=status,
        tokens=estimate_tokens(text),
        wall_time_ms=wall_time_ms,
        timeout=timeout,
        repeat_count=repeat_count,
        guard_passed=guard_passed and not timeout,
        reason=reason,
        payload={"content_hash": hash_text(text), "sanitized_snippet": text},
    )


def _rtk_fixture_candidate(
    input_text: str,
    output_text: str,
    *,
    must_preserve: tuple[str, ...] = (),
) -> MethodMeasurement:
    from .adapters import RTKAdapter

    measured = RTKAdapter(runner=lambda text: output_text).measure(
        input_text,
        Lane.COMMAND_OUTPUT,
        must_preserve=must_preserve,
    )
    payload = {
        **(measured.payload or {}),
        "sanitized_snippet": output_text,
    }
    return replace(
        measured,
        reason="fixture replay via injected safe runner",
        payload=payload,
    )


def _native_command_candidate(
    input_text: str,
    *,
    must_preserve: tuple[str, ...],
) -> MethodMeasurement:
    from .native_command import FlowTrimNativeCommand

    return FlowTrimNativeCommand().measure(
        input_text,
        Lane.COMMAND_OUTPUT,
        must_preserve=must_preserve,
    )


def _enforce_method_preservation(
    methods: list[MethodMeasurement],
    must_preserve: tuple[str, ...],
) -> list[MethodMeasurement]:
    if not must_preserve:
        return methods

    enforced = []
    for method in methods:
        snippet = (method.payload or {}).get("sanitized_snippet")
        if not isinstance(snippet, str):
            enforced.append(
                replace(
                    method,
                    guard_passed=False,
                    reason="missing preservation text for candidate",
                )
            )
            continue

        missing = [item for item in must_preserve if item and item not in snippet]
        if missing:
            enforced.append(
                replace(
                    method,
                    guard_passed=False,
                    reason="missing required items: " + ", ".join(missing),
                )
            )
        else:
            enforced.append(method)

    return enforced


def _preservation_for(
    original: str,
    candidate: str,
    must_preserve: tuple[str, ...],
) -> PreservationSummary:
    missing = [item for item in must_preserve if item and item not in candidate]
    return PreservationSummary(not missing, missing)


def _with_runtime_and_payload(
    case: BenchmarkCase,
    runtime_changes: RuntimeChanges,
    payload: dict[str, Any] | None,
) -> BenchmarkCase:
    if payload is None:
        return replace(case, runtime_changes=runtime_changes)

    methods = []
    for method in case.methods:
        if method.method == "raw":
            methods.append(
                replace(method, payload={**(method.payload or {}), **payload})
            )
        else:
            methods.append(method)
    return replace(case, methods=methods, runtime_changes=runtime_changes)


def _aql_readonly_audit(
    aql_root: str | Path | None,
) -> tuple[dict[str, Any] | None, RuntimeChanges]:
    if aql_root is None:
        return None, RuntimeChanges()

    root = Path(aql_root)
    if not root.exists():
        return (
            {
                "command": "git status --short",
                "reason": "aql root unavailable for read-only audit",
            },
            RuntimeChanges(),
        )

    pre_status = _run_readonly_git_status(root)
    post_status = _run_readonly_git_status(root)
    payload = {
        "command": "git status --short",
        "pre_status_hash": _safe_hash(pre_status),
        "post_status_hash": _safe_hash(post_status),
    }
    runtime_changes = RuntimeChanges(
        unapproved_filesystem_writes=pre_status != post_status
    )
    return payload, runtime_changes


def _run_readonly_git_status(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "status", "--short"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    return (result.stdout or result.stderr or "").strip()


def _safe_hash(text: str) -> str:
    from .adapters import hash_text

    return hash_text(text)


def _tool_infos(
    *,
    which: Any = shutil.which,
    version_runner: Any | None = None,
) -> list[ToolInfo]:
    version_runner = version_runner or _tool_version
    rtk_path = which("rtk")
    headroom_path = which("headroom")
    return [
        ToolInfo(
            name="rtk",
            available=rtk_path is not None,
            version=version_runner(rtk_path) if rtk_path else None,
            reason=None if rtk_path else "not installed on PATH",
        ),
        ToolInfo(
            name="headroom",
            available=headroom_path is not None,
            version=version_runner(headroom_path) if headroom_path else None,
            reason=None if headroom_path else "not installed on PATH",
        ),
    ]


def _tool_version(path: str) -> str | None:
    try:
        result = subprocess.run(
            [path, "--version"],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
            timeout=1,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    output = (result.stdout or result.stderr or "").strip()
    return output or None


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
        return _select_raw(
            case,
            raw.method,
            "raw-over-wall-time-budget",
            counts_as_claim=False,
        )

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

    if isinstance(payload, str) and scan_text(payload):
        raise ValueError("unsafe payload value")


def _assert_safe_report_text(text: str) -> None:
    if scan_text(text):
        raise ValueError("unsafe report text")
