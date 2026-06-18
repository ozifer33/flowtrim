from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DecisionLabel(StrEnum):
    NATIVE_WIN = "native-win"
    BASELINE_WIN = "baseline-win"
    RAW_WIN = "raw-win"
    INSUFFICIENT_EVIDENCE = "insufficient-evidence"
    SKIPPED_NEUTRAL = "skipped-neutral"


@dataclass(frozen=True)
class ScorecardResult:
    label: DecisionLabel
    selected_method: str | None
    primary_delta: int
    reason: str


def compare_token_methods(
    *,
    raw_tokens: int,
    native_tokens: int | None,
    baseline_tokens: int | None,
    native_guard_passed: bool,
    baseline_guard_passed: bool,
    native_wall_time_ms: int,
    baseline_wall_time_ms: int,
    wall_time_budget_ms: int,
    raw_short_token_limit: int = 8,
) -> ScorecardResult:
    if raw_tokens <= raw_short_token_limit:
        return ScorecardResult(DecisionLabel.RAW_WIN, "raw", 0, "raw-short-output")

    native_can_win = (
        native_tokens is not None
        and native_guard_passed
        and native_wall_time_ms <= wall_time_budget_ms
        and native_tokens < raw_tokens
    )
    baseline_can_win = (
        baseline_tokens is not None
        and baseline_guard_passed
        and baseline_wall_time_ms <= wall_time_budget_ms
        and baseline_tokens < raw_tokens
    )

    candidates: list[tuple[int, int, str, DecisionLabel]] = []
    if native_can_win and native_tokens is not None:
        candidates.append(
            (
                native_tokens,
                native_wall_time_ms,
                "flowtrim-native-command",
                DecisionLabel.NATIVE_WIN,
            )
        )
    if baseline_can_win and baseline_tokens is not None:
        candidates.append((baseline_tokens, baseline_wall_time_ms, "rtk", DecisionLabel.BASELINE_WIN))

    if candidates:
        tokens, _wall_time, method, label = min(
            candidates, key=lambda item: (item[0], item[1], item[2])
        )
        return ScorecardResult(label, method, raw_tokens - tokens, "lower-token-safe")

    smaller_failed_guard = (
        native_tokens is not None
        and native_tokens < raw_tokens
        and not native_guard_passed
    ) or (
        baseline_tokens is not None
        and baseline_tokens < raw_tokens
        and not baseline_guard_passed
    )
    if smaller_failed_guard:
        return ScorecardResult(
            DecisionLabel.INSUFFICIENT_EVIDENCE,
            None,
            0,
            "guard-failed",
        )

    return ScorecardResult(DecisionLabel.RAW_WIN, "raw", 0, "raw-best")
