from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PreservationReport:
    passed: bool
    missing: tuple[str, ...]

    @property
    def reason(self) -> str:
        if self.passed:
            return "all required items preserved"
        return "missing required items: " + ", ".join(self.missing)


def check_preservation(
    original: str,
    candidate: str,
    must_preserve: tuple[str, ...],
) -> PreservationReport:
    missing = tuple(item for item in must_preserve if item and item not in candidate)
    return PreservationReport(passed=not missing, missing=missing)
