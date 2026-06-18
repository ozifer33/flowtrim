from __future__ import annotations

from .models import Lane, MethodResult


def select_best_method(lane: Lane, results: list[MethodResult]) -> MethodResult:
    if not results:
        raise ValueError("results must not be empty")

    raw = next((result for result in results if result.method == "raw" and result.lane == lane), None)
    if raw is None:
        raise ValueError(f"select_best_method requires a raw fallback for lane {lane}")

    if lane == Lane.EXACT_EVIDENCE:
        return raw

    valid_results = [result for result in results if result.valid and result.lane == lane]
    if not valid_results:
        return raw

    return min(valid_results, key=lambda result: (result.tokens, result.wall_time_ms, result.method))
