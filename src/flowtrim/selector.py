from __future__ import annotations

from .models import Lane, MethodResult


LANE_WALL_TIME_BUDGET_MS = {
    Lane.REPO_CONTEXT: 500,
    Lane.COMMAND_OUTPUT: 250,
    Lane.CODE_GENERATION: 500,
    Lane.LONG_CONTEXT: 500,
    Lane.EXACT_EVIDENCE: 0,
}


def select_best_method(lane: Lane, results: list[MethodResult]) -> MethodResult:
    if not results:
        raise ValueError("results must not be empty")

    raw = next((result for result in results if result.method == "raw" and result.lane == lane), None)
    if raw is None:
        raise ValueError(f"select_best_method requires a raw fallback for lane {lane}")

    if lane == Lane.EXACT_EVIDENCE:
        return raw

    wall_time_budget_ms = LANE_WALL_TIME_BUDGET_MS[lane]
    candidate_results = [
        result
        for result in results
        if result.valid
        and result.lane == lane
        and result.method != "raw"
        and result.wall_time_ms <= wall_time_budget_ms
        and result.tokens < raw.tokens
    ]
    if not candidate_results:
        return raw

    return min(candidate_results, key=lambda result: (result.tokens, result.wall_time_ms, result.method))
