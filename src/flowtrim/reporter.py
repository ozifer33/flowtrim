from __future__ import annotations

import json

from .models import MethodResult


def report_json(result: MethodResult) -> str:
    guard_passed = result.guard_passed
    payload = {
        "schema": "flowtrim-decision/v1",
        "status": "selected" if guard_passed else "insufficient-evidence",
        "lane": result.lane.value,
        "selected_method": result.method,
        "tokens": result.tokens,
        "baseline_tokens": result.baseline_tokens,
        "savings_vs_baseline": result.savings_vs_baseline if guard_passed else None,
        "wall_time_ms": result.wall_time_ms,
        "guard_passed": guard_passed,
        "reason": result.reason,
        "runtime_changes": "none",
    }
    return json.dumps(payload, sort_keys=True)


def report_text(result: MethodResult) -> str:
    token_delta = (
        f"{result.savings_vs_baseline:.2%}"
        if result.guard_passed
        else "insufficient-evidence"
    )
    return "\n".join(
        [
            "FlowTrim decision:",
            f"Lane: {result.lane.value}",
            f"Selected method: {result.method}",
            f"Token delta: {token_delta}",
            f"Wall-time: {result.wall_time_ms} ms",
            f"Preservation checks: {'pass' if result.guard_passed else 'fail'}",
            f"Reason: {result.reason}",
            "Runtime changes: none",
        ]
    )
