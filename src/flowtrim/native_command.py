from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .adapters import hash_text, median_measure
from .benchmark import BenchmarkStatus, MethodMeasurement
from .metrics import estimate_tokens
from .models import Lane


METHOD = "flowtrim-native-command"
URL_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.IGNORECASE)
PATH_RE = re.compile(r"\b(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.:-]+\b")
PYTEST_TEST_RE = re.compile(r"\b(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+::[A-Za-z0-9_:\[\]-]+\b")
FAILING_TEST_PATTERNS = (
    # go test
    re.compile(r"^--- FAIL: (\S+)", re.MULTILINE),
    # cargo test
    re.compile(r"^test ([A-Za-z0-9_:]+) \.\.\. FAILED\s*$", re.MULTILINE),
    # jest / vitest / mocha-style cross or bullet markers
    re.compile(r"^\s*[✕✗×●] (.+?)(?:\s+\(\d+\s*m?s\))?\s*$", re.MULTILINE),
    # generic "FAIL <target>" lines (jest suites, pytest short summary, go packages)
    re.compile(r"^\s*FAIL(?:ED)?[ :\t]+(\S+)(?:\s.*)?$", re.MULTILINE),
)
ERROR_RE = re.compile(r"\b[A-Z][A-Za-z0-9_]*(?:Error|Exception|Exceeded|Failure|Failed)\b")
ERROR_LINE_RE = re.compile(
    r"^.*(?:\berror\b\s*[:!]|\bERROR\b|npm ERR!|panic:|panicked at|FATAL"
    r"|error TS\d+|\berror\[[A-Z0-9]+\]).*$",
    re.MULTILINE,
)
SUMMARY_PATTERNS = (
    # pytest / generic "N passed", "N failed", "N errors"
    re.compile(r"\b\d+\s+(?:passed|failed|errors?)\b", re.IGNORECASE),
    # jest "Tests: 1 failed, 5 passed, 6 total"
    re.compile(r"\bTests?:\s+[^\n]*\btotal\b", re.IGNORECASE),
    # cargo "test result: FAILED. 3 passed; 1 failed; ..."
    re.compile(r"\btest result: [^\n]+", re.IGNORECASE),
    # tsc "Found 3 errors"
    re.compile(r"\bFound \d+ errors?\b", re.IGNORECASE),
)
FAIL_TEXT_PATTERNS = (
    re.compile(r"\b[1-9]\d*\s+failed\b", re.IGNORECASE),
    re.compile(r"^FAIL\b", re.MULTILINE),
    re.compile(r"npm ERR!"),
    re.compile(r"\bpanic:"),
    re.compile(r"\bFound [1-9]\d* errors?\b", re.IGNORECASE),
    re.compile(r"\btest result: FAILED\b", re.IGNORECASE),
)
PASS_TEXT_PATTERNS = (
    re.compile(r"\b[1-9]\d*\s+passed\b", re.IGNORECASE),
    re.compile(r"^ok\b", re.MULTILINE),
    re.compile(r"\btest result: ok\b", re.IGNORECASE),
    re.compile(r"\bBUILD SUCCESS\b", re.IGNORECASE),
    re.compile(r"\bcompiled successfully\b", re.IGNORECASE),
)
NOISE_MARKERS = ("INFO noise:", "chunk", "cache warmed", "completed")
REPEATED_TEMPLATE_THRESHOLD = 3
TEMPLATE_DIGIT_RE = re.compile(r"\d+")
MAX_PACKET_ITEMS = 5
MAX_ERROR_LINES = 3
MAX_ERROR_LINE_CHARS = 160
PACKET_FIELDS = (
    ("failing_tests", "failing tests"),
    ("error_labels", "errors"),
    ("error_lines", "error lines"),
    ("summary_lines", "summary"),
    ("primary_files", "files"),
)


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
    status_override: str | None = None,
) -> NativeCommandPacket:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    failing_tests = _failing_tests(text, lines)
    status = status_override or _status(text, lines, failing_tests)
    payload = {
        "content_hash": hash_text(text),
        "status": status,
        "primary_files": _file_paths(text)[:MAX_PACKET_ITEMS],
        "failing_tests": failing_tests[:MAX_PACKET_ITEMS],
        "error_labels": _unique(ERROR_RE.findall(text))[:MAX_PACKET_ITEMS],
        "error_lines": _error_lines(text, lines)[:MAX_ERROR_LINES],
        "summary_lines": _summary_lines(text)[:MAX_PACKET_ITEMS],
        "omitted_noise_classes": _omitted_noise_classes(lines),
        "must_keep": list(must_preserve),
    }
    # Only facts that exist in the source may be rendered; items missing from
    # the source must fail the guard instead of being fabricated into the packet.
    present_items = [item for item in must_preserve if item and item in text]
    packet_text = _render_packet_text({**payload, "must_keep": present_items})
    payload["sanitized_snippet"] = packet_text
    missing = [item for item in must_preserve if item and item not in packet_text]
    return NativeCommandPacket(
        text=packet_text,
        payload=payload,
        guard_passed=not missing,
        reason=None if not missing else "missing required items: " + ", ".join(missing),
    )


def _render_packet_text(payload: dict[str, Any]) -> str:
    lines = [f"status: {payload['status']}"]
    for key, label in PACKET_FIELDS:
        values = payload.get(key) or []
        if values:
            lines.append(f"{label}: " + ", ".join(values))
    preserved = [item for item in payload.get("must_keep", ()) if item]
    missing_from_packet = [
        item for item in preserved if not any(item in line for line in lines)
    ]
    if missing_from_packet:
        lines.append("must-keep: " + ", ".join(dict.fromkeys(missing_from_packet)))
    omitted = payload.get("omitted_noise_classes") or []
    if omitted:
        lines.append("omitted: " + ", ".join(omitted))
    lines.append(f"raw-hash: {payload['content_hash']}")
    return "\n".join(lines)


def _status(text: str, lines: list[str], failing_tests: list[str]) -> str:
    if failing_tests:
        return "fail"
    lowered = text.lower()
    if (
        any(pattern.search(text) for pattern in FAIL_TEXT_PATTERNS)
        or any(_line_is_failure_marker(line) for line in lines)
        or "error keep:" in lowered
    ):
        return "fail"
    if any(pattern.search(text) for pattern in PASS_TEXT_PATTERNS) or "passed" in lowered:
        return "pass"
    if "warn" in lowered:
        return "warning"
    return "unknown"


def _line_is_failure_marker(line: str) -> bool:
    upper = line.upper()
    return upper.endswith(" FAILED") and not re.search(r"\b0\s+FAILED\b", upper)


def _file_paths(text: str) -> list[str]:
    without_urls = URL_RE.sub(" ", text)
    paths = []
    for value in PATH_RE.findall(without_urls):
        path = value.split(":", 1)[0]
        if not any(character.isalpha() for character in path):
            continue
        paths.append(path)
    return _unique(paths)


def _failing_tests(text: str, lines: list[str]) -> list[str]:
    tests = []
    for line in lines:
        if "FAILED" in line:
            tests.extend(PYTEST_TEST_RE.findall(line))
    for pattern in FAILING_TEST_PATTERNS:
        tests.extend(match.strip() for match in pattern.findall(text))
    return _unique([test for test in tests if test])


def _error_lines(text: str, lines: list[str]) -> list[str]:
    found = []
    for match in ERROR_LINE_RE.findall(text):
        stripped = match.strip()
        if stripped:
            found.append(stripped[:MAX_ERROR_LINE_CHARS])
    return _unique(found)


def _summary_lines(text: str) -> list[str]:
    facts = []
    for pattern in SUMMARY_PATTERNS:
        facts.extend(match.strip() for match in pattern.findall(text))
    return _unique(facts)


def _omitted_noise_classes(lines: list[str]) -> list[str]:
    classes = []
    if any(any(marker in line for marker in NOISE_MARKERS) for line in lines):
        classes.append("progress-noise")
    if len(lines) != len(set(lines)):
        classes.append("duplicate-lines")
    if _has_repeated_templates(lines):
        classes.append("repeated-templates")
    return classes


def _has_repeated_templates(lines: list[str]) -> bool:
    counts: dict[str, int] = {}
    for line in lines:
        template = TEMPLATE_DIGIT_RE.sub("#", line)
        counts[template] = counts.get(template, 0) + 1
        if counts[template] >= REPEATED_TEMPLATE_THRESHOLD:
            return True
    return False


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
