from __future__ import annotations

from .models import Lane


PRIMARY_METRICS: dict[Lane, str] = {
    Lane.REPO_CONTEXT: "files_and_tokens_read",
    Lane.COMMAND_OUTPUT: "output_tokens",
    Lane.CODE_GENERATION: "generated_tokens",
    Lane.LONG_CONTEXT: "input_tokens",
    Lane.EXACT_EVIDENCE: "raw_required",
}


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return (len(text) + 3) // 4


def savings_ratio(baseline_tokens: int, candidate_tokens: int) -> float:
    if baseline_tokens <= 0:
        return 0.0
    return round((baseline_tokens - candidate_tokens) / baseline_tokens, 4)


def lane_primary_metric(lane: Lane) -> str:
    return PRIMARY_METRICS[lane]
