from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .adapters import hash_text, median_measure
from .benchmark import BenchmarkStatus, MethodMeasurement
from .metrics import estimate_tokens
from .models import Lane


METHOD = "flowtrim-native-command"
PATH_RE = re.compile(r"\b(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.:-]+\b")
TEST_RE = re.compile(r"\b(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+::[A-Za-z0-9_:-]+\b")
ERROR_RE = re.compile(r"\b[A-Z][A-Za-z0-9_]*(?:Error|Exception|Exceeded|Failure|Failed)\b")
SUMMARY_RE = re.compile(r"\b\d+\s+(?:passed|failed|errors?)\b", re.IGNORECASE)
NOISE_MARKERS = ("INFO noise:", "chunk", "cache warmed", "completed")


@dataclass(frozen=True)
class NativeCommandPacket:
    text: str
    payload: dict[str, Any]
    guard_passed: bool
    reason: str | None


class FlowTrimNativeCommand:
    def measure(
        self,
        text: str,
        lane: Lane,
        *,
        must_preserve: tuple[str, ...] = (),
        repeat_count: int = 3,
        timeout_ms: int = 250,
    ) -> MethodMeasurement:
        timing = median_measure(
            lambda: compact_command_output(text, must_preserve=must_preserve),
            repeat_count,
            timeout_ms,
        )
        packet: NativeCommandPacket = timing.value
        return MethodMeasurement(
            method=METHOD,
            status=BenchmarkStatus.TIMEOUT if timing.timeout else BenchmarkStatus.OK,
            tokens=estimate_tokens(packet.text),
            wall_time_ms=timing.wall_time_ms,
            timeout=timing.timeout,
            repeat_count=timing.repeat_count,
            guard_passed=packet.guard_passed and not timing.timeout,
            reason=packet.reason if not timing.timeout else "timeout",
            payload=packet.payload,
        )


def compact_command_output(
    text: str,
    *,
    must_preserve: tuple[str, ...] = (),
) -> NativeCommandPacket:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    primary_files = _file_paths(text)
    failing_tests = _failing_tests(lines)
    error_labels = _unique(ERROR_RE.findall(text))
    summary_facts = _unique(SUMMARY_RE.findall(text))
    status = _status(text, lines)
    omitted = _omitted_noise_classes(lines)

    preserved_items = _minimal_preserved_items(
        [item for item in must_preserve if item and item in text]
    )
    facts = [status, *preserved_items, *error_labels[:1], *failing_tests[:1]]
    snippet = " ".join(_unique([fact for fact in facts if fact and fact != "unknown"]))
    missing = [item for item in must_preserve if item and item not in snippet]
    payload = {
        "content_hash": hash_text(text),
        "status": status,
        "primary_files": primary_files[:5],
        "failing_tests": failing_tests[:5],
        "error_labels": error_labels[:5],
        "summary_lines": summary_facts[:5],
        "omitted_noise_classes": omitted,
        "must_keep": list(must_preserve),
        "sanitized_snippet": snippet,
    }
    return NativeCommandPacket(
        text=snippet,
        payload=payload,
        guard_passed=not missing,
        reason=None if not missing else "missing required items: " + ", ".join(missing),
    )


def _status(text: str, lines: list[str]) -> str:
    lowered = text.lower()
    if (
        re.search(r"\b[1-9]\d*\s+failed\b", lowered)
        or any(_line_is_failure_marker(line) for line in lines)
        or "error keep:" in lowered
    ):
        return "fail"
    if "passed" in lowered:
        return "pass"
    if "warn" in lowered:
        return "warning"
    return "unknown"


def _line_is_failure_marker(line: str) -> bool:
    upper = line.upper()
    return upper.endswith(" FAILED") and not re.search(r"\b0\s+FAILED\b", upper)


def _file_paths(text: str) -> list[str]:
    paths = []
    for value in PATH_RE.findall(text):
        paths.append(value.split(":", 1)[0])
    return _unique(paths)


def _failing_tests(lines: list[str]) -> list[str]:
    tests = []
    for line in lines:
        if "FAILED" in line:
            tests.extend(TEST_RE.findall(line))
    return _unique(tests)


def _omitted_noise_classes(lines: list[str]) -> list[str]:
    classes = []
    if any(any(marker in line for marker in NOISE_MARKERS) for line in lines):
        classes.append("progress-noise")
    if len(lines) != len(set(lines)):
        classes.append("duplicate-lines")
    return classes


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _minimal_preserved_items(items: list[str]) -> list[str]:
    unique_items = _unique(items)
    return [
        item
        for item in unique_items
        if not any(item != other and item in other for other in unique_items)
    ]
