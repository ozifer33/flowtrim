from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .benchmark import SCHEMA
from .privacy import scan_text


COMPARISON_SCHEMA = "flowtrim-comparison/v1"
NATIVE_METHOD = "flowtrim-native-command"
COUNTED_WINNERS = ("raw", "rtk", NATIVE_METHOD, "headroom-direct", "ponytail-lens")


def compare_reports(
    baseline_report: str | Path,
    candidate_report: str | Path,
    *,
    focus: str = "headroom-direct",
) -> dict[str, Any]:
    baseline = _load_report_json(baseline_report)
    candidate = _load_report_json(candidate_report)
    _validate_compatible_reports(baseline, candidate)

    baseline_cases = _cases_by_id(baseline)
    candidate_cases = _cases_by_id(candidate)
    focus_totals = {
        "measured": 0,
        "skipped": 0,
        "timeout": 0,
        "guard_failed": 0,
        "selected": 0,
        "tokens": 0,
    }
    winner_totals = {method: 0 for method in COUNTED_WINNERS}
    winner_totals["other"] = 0
    token_delta = {
        "candidate_selected_vs_baseline_selected": 0,
        "focus_vs_raw": 0,
    }

    for case_id, candidate_case in candidate_cases.items():
        baseline_case = baseline_cases[case_id]
        selected = candidate_case.get("selected_method")
        if selected in winner_totals:
            winner_totals[selected] += 1
        elif selected:
            winner_totals["other"] += 1

        focus_method = _method(candidate_case, focus)
        if focus_method is not None:
            _count_focus_method(focus_totals, focus_method)
            raw = _method(candidate_case, "raw")
            if raw is not None and _is_token_delta_comparable(focus_method):
                token_delta["focus_vs_raw"] += int(raw.get("tokens", 0)) - int(
                    focus_method.get("tokens", 0)
                )

        baseline_selected = _method(baseline_case, baseline_case.get("selected_method"))
        candidate_selected = _method(candidate_case, selected)
        if baseline_selected is not None and candidate_selected is not None:
            token_delta["candidate_selected_vs_baseline_selected"] += int(
                baseline_selected.get("tokens", 0)
            ) - int(candidate_selected.get("tokens", 0))

    summary = {
        "schema": COMPARISON_SCHEMA,
        "profile": candidate["profile"],
        "focus": focus,
        "cases_matched": len(candidate_cases),
        "focus_totals": focus_totals,
        "winner_totals": winner_totals,
        "token_delta": token_delta,
        "runtime_changes": candidate.get("runtime_changes", {}),
        "claim_guidance": _claim_guidance(focus_totals, winner_totals, focus),
    }
    _assert_safe_summary(summary)
    return summary


def compare_reports_to_json(summary: dict[str, Any]) -> str:
    text = json.dumps(summary, indent=2, sort_keys=True)
    _assert_safe_text(text)
    return text


def compare_reports_to_markdown(summary: dict[str, Any]) -> str:
    focus_totals = summary["focus_totals"]
    winner_totals = summary["winner_totals"]
    token_delta = summary["token_delta"]
    lines = [
        "# FlowTrim Comparison",
        "",
        f"Profile: {summary['profile']}",
        f"Focus: {summary['focus']}",
        f"Cases matched: {summary['cases_matched']}",
        "",
        "## Headroom",
        "",
        f"- measured: {focus_totals['measured']}",
        f"- skipped: {focus_totals['skipped']}",
        f"- timeout: {focus_totals['timeout']}",
        f"- guard failed: {focus_totals['guard_failed']}",
        f"- selected: {focus_totals['selected']}",
        "",
        "## Winners",
        "",
        f"- raw: {winner_totals['raw']}",
        f"- rtk: {winner_totals['rtk']}",
        f"- flowtrim-native-command: {winner_totals[NATIVE_METHOD]}",
        f"- headroom-direct: {winner_totals['headroom-direct']}",
        f"- ponytail-lens: {winner_totals['ponytail-lens']}",
        f"- other: {winner_totals['other']}",
        "",
        "## Token Deltas",
        "",
        f"- candidate selected vs baseline selected: {token_delta['candidate_selected_vs_baseline_selected']}",
        f"- focus vs raw: {token_delta['focus_vs_raw']}",
        "",
        f"Guidance: {summary['claim_guidance']}",
    ]
    text = "\n".join(lines)
    _assert_safe_text(text)
    return text


def _load_report_json(path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid report json") from exc
    if not isinstance(data, dict):
        raise ValueError("invalid report json")
    return data


def _validate_compatible_reports(baseline: dict[str, Any], candidate: dict[str, Any]) -> None:
    if baseline.get("schema") != SCHEMA or candidate.get("schema") != SCHEMA:
        raise ValueError("schema mismatch")
    if baseline.get("profile") != candidate.get("profile"):
        raise ValueError("profile mismatch")
    if set(_cases_by_id(baseline)) != set(_cases_by_id(candidate)):
        raise ValueError("case id mismatch")


def _cases_by_id(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise ValueError("invalid report json")
    return {str(case.get("case_id")): case for case in cases}


def _method(case: dict[str, Any], method_name: str | None) -> dict[str, Any] | None:
    if not method_name:
        return None
    for method in case.get("methods", []):
        if method.get("method") == method_name:
            return method
    return None


def _count_focus_method(totals: dict[str, int], method: dict[str, Any]) -> None:
    status = method.get("status")
    guard_passed = bool(method.get("guard_passed"))
    tokens = int(method.get("tokens", 0))
    if status == "skipped":
        totals["skipped"] += 1
        return
    if status == "timeout":
        totals["timeout"] += 1
        return
    totals["tokens"] += tokens
    totals["measured"] += 1
    if status == "selected":
        totals["selected"] += 1
    if not guard_passed:
        totals["guard_failed"] += 1


def _is_token_delta_comparable(method: dict[str, Any]) -> bool:
    return method.get("status") not in {"skipped", "timeout"} and bool(
        method.get("guard_passed")
    )


def _claim_guidance(
    focus_totals: dict[str, int],
    winner_totals: dict[str, int],
    focus: str,
) -> str:
    if focus_totals["measured"] == 0:
        return f"{focus} unavailable or skipped; do not claim a comparison result."
    if winner_totals.get(focus, 0) == 0:
        return f"{focus} measured with no safe wins on this corpus."
    return f"{focus} won measured cases on this pinned corpus only."


def _assert_safe_summary(summary: dict[str, Any]) -> None:
    _assert_safe_text(json.dumps(summary, sort_keys=True))


def _assert_safe_text(text: str) -> None:
    findings = scan_text(text)
    if findings:
        raise ValueError("unsafe comparison text")
