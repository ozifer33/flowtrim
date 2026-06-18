from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Lane(StrEnum):
    REPO_CONTEXT = "repo-context"
    COMMAND_OUTPUT = "command-output"
    CODE_GENERATION = "code-generation"
    LONG_CONTEXT = "long-context"
    EXACT_EVIDENCE = "exact-evidence"


@dataclass(frozen=True)
class MethodResult:
    method: str
    lane: Lane
    tokens: int
    baseline_tokens: int
    wall_time_ms: int
    guard_passed: bool
    reason: str
    required_items: tuple[str, ...] = field(default_factory=tuple)

    @property
    def savings_vs_baseline(self) -> float:
        if self.baseline_tokens <= 0:
            return 0.0
        return round((self.baseline_tokens - self.tokens) / self.baseline_tokens, 4)

    @property
    def valid(self) -> bool:
        return self.guard_passed


@dataclass(frozen=True)
class LaneTask:
    lane: Lane
    name: str
    read_set: frozenset[str]
    write_set: frozenset[str] = field(default_factory=frozenset)

    @property
    def read_only(self) -> bool:
        return not self.write_set
