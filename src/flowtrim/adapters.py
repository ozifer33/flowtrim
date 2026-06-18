from __future__ import annotations

import hashlib
import json
import shutil
import statistics
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .benchmark import BenchmarkStatus, MethodMeasurement
from .metrics import estimate_tokens
from .models import Lane


DEFAULT_REPEAT_COUNT = 3
DEFAULT_FIXTURE_TIMEOUT_MS = 250
DEFAULT_CODE_LENS_TIMEOUT_MS = 500
DEFAULT_VERSION_TIMEOUT_MS = 500


@dataclass(frozen=True)
class MedianMeasurement:
    value: Any
    wall_time_ms: int
    timeout: bool
    repeat_count: int


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def median_measure(
    callable: Callable[[], Any],
    repeat_count: int,
    timeout_ms: int,
) -> MedianMeasurement:
    if repeat_count < 1:
        raise ValueError("repeat_count must be at least 1")

    elapsed_times: list[int] = []
    last_value: Any = None
    timed_out = False

    for _ in range(repeat_count):
        started_at = time.perf_counter()
        last_value = callable()
        elapsed_ms = int(round((time.perf_counter() - started_at) * 1000))
        elapsed_times.append(max(elapsed_ms, 0))
        if elapsed_ms > timeout_ms:
            timed_out = True

    return MedianMeasurement(
        value=last_value,
        wall_time_ms=int(statistics.median(elapsed_times)),
        timeout=timed_out,
        repeat_count=repeat_count,
    )


class RawAdapter:
    def measure(
        self,
        text: str,
        lane: Lane,
        *,
        repeat_count: int = DEFAULT_REPEAT_COUNT,
        timeout_ms: int = DEFAULT_FIXTURE_TIMEOUT_MS,
    ) -> MethodMeasurement:
        timing = median_measure(lambda: text, repeat_count, timeout_ms)
        return MethodMeasurement(
            method="raw",
            status=BenchmarkStatus.TIMEOUT if timing.timeout else BenchmarkStatus.OK,
            tokens=estimate_tokens(text),
            wall_time_ms=timing.wall_time_ms,
            timeout=timing.timeout,
            repeat_count=timing.repeat_count,
            guard_passed=not timing.timeout,
            reason=None if not timing.timeout else "timeout",
            payload={"content_hash": hash_text(text)},
        )


class RTKAdapter:
    def __init__(
        self,
        *,
        executable: str | None = None,
        runner: Callable[[str], Any] | None = None,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self.executable = executable or "rtk"
        self.runner = runner
        self.which = which

    def measure(
        self,
        text: str,
        lane: Lane,
        *,
        must_preserve: Sequence[str] = (),
        repeat_count: int = DEFAULT_REPEAT_COUNT,
        timeout_ms: int = DEFAULT_FIXTURE_TIMEOUT_MS,
    ) -> MethodMeasurement:
        if self.runner is None:
            if self.which(self.executable) is None:
                return _skipped_measurement(
                    "rtk",
                    reason=f"{self.executable} executable not found",
                )
            return _skipped_measurement(
                "rtk",
                reason="rtk runner not provided for safe adapter",
            )

        timing = median_measure(
            lambda: _coerce_runner_output(self.runner(text)),
            repeat_count,
            timeout_ms,
        )
        output = timing.value or ""
        missing = _missing_required_items(output, must_preserve)
        guard_passed = not missing and not timing.timeout
        reason = None
        if missing:
            reason = "missing required items: " + ", ".join(missing)
        elif timing.timeout:
            reason = "timeout"

        return MethodMeasurement(
            method="rtk",
            status=BenchmarkStatus.TIMEOUT if timing.timeout else BenchmarkStatus.OK,
            tokens=estimate_tokens(output),
            wall_time_ms=timing.wall_time_ms,
            timeout=timing.timeout,
            repeat_count=timing.repeat_count,
            guard_passed=guard_passed,
            reason=reason,
            payload={"content_hash": hash_text(output)},
        )


class HeadroomAdapter:
    def __init__(
        self,
        *,
        executable: str | None = None,
        which: Callable[[str], str | None] = shutil.which,
        version_runner: Callable[[str], str | None] | None = None,
    ) -> None:
        self.executable = executable or "headroom"
        self.which = which
        self.version_runner = version_runner or _run_version

    def measure(
        self,
        text: str,
        lane: Lane,
        *,
        repeat_count: int = 0,
    ) -> MethodMeasurement:
        resolved = self.which(self.executable)
        if resolved is None:
            return _skipped_measurement(
                "headroom-direct",
                reason=f"{self.executable} executable not found",
                repeat_count=repeat_count,
            )

        version = self.version_runner(resolved)
        payload = {"version": version} if version else None
        return _skipped_measurement(
            "headroom-direct",
            reason="headroom safe adapter only performs availability/version checks",
            repeat_count=repeat_count,
            payload=payload,
        )


class PonytailLens:
    def analyze(
        self,
        text: str,
        *,
        must_keep: Sequence[str] = (),
        tests: Sequence[str] = (),
        repeat_count: int = DEFAULT_REPEAT_COUNT,
        timeout_ms: int = DEFAULT_CODE_LENS_TIMEOUT_MS,
    ) -> MethodMeasurement:
        timing = median_measure(
            lambda: _build_code_lens_payload(text, must_keep, tests),
            repeat_count,
            timeout_ms,
        )
        payload = timing.value
        has_violation = bool(payload["must_keep_violation"])
        return MethodMeasurement(
            method="ponytail-lens",
            status=BenchmarkStatus.TIMEOUT if timing.timeout else BenchmarkStatus.OK,
            tokens=estimate_tokens(json.dumps(payload, sort_keys=True)),
            wall_time_ms=timing.wall_time_ms,
            timeout=timing.timeout,
            repeat_count=timing.repeat_count,
            guard_passed=not has_violation and not timing.timeout,
            reason="must_keep/test surface violation" if has_violation else None,
            payload=payload,
        )


def _skipped_measurement(
    method: str,
    *,
    reason: str,
    repeat_count: int = 0,
    payload: dict[str, Any] | None = None,
) -> MethodMeasurement:
    return MethodMeasurement(
        method=method,
        status=BenchmarkStatus.SKIPPED,
        tokens=0,
        wall_time_ms=0,
        timeout=False,
        repeat_count=repeat_count,
        guard_passed=False,
        reason=reason,
        payload=payload,
    )


def _coerce_runner_output(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "stdout"):
        stdout = getattr(value, "stdout") or ""
        return _coerce_runner_output(stdout)
    return str(value)


def _missing_required_items(
    candidate: str,
    must_preserve: Sequence[str],
) -> tuple[str, ...]:
    return tuple(item for item in must_preserve if item and item not in candidate)


def _run_version(executable: str) -> str | None:
    try:
        result = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=DEFAULT_VERSION_TIMEOUT_MS / 1000,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    output = (result.stdout or result.stderr or "").strip()
    return output or None


DELETE_HINTS = (
    "delete",
    "remove",
    "duplicate",
    "over-abstract",
    "overabstract",
    "wrapper",
    "unused",
    "dead code",
    "redundant",
)


def _build_code_lens_payload(
    text: str,
    must_keep: Sequence[str],
    tests: Sequence[str],
) -> dict[str, Any]:
    items = [
        _delete_item_for_line(line.strip(), must_keep, tests)
        for line in text.splitlines()
        if _looks_like_delete_candidate(line)
    ]
    if not items:
        items.append(
            {
                "item": "no obvious deletion candidate",
                "severity": "watch",
                "rationale": "No deterministic delete signal was found.",
                "estimated_loc_delta": 0,
                "requirement_affected": False,
                "test_surface_affected": False,
                "must_keep_violation": False,
            }
        )

    requirement_affected = any(
        item["requirement_affected"] != "none" for item in items
    )
    test_surface_affected = any(
        item["test_surface_affected"] != "none" for item in items
    )
    must_keep_violation = any(item["must_keep_violation"] for item in items)
    return {
        "content_hash": hash_text(text),
        "delete_items": items,
        "generated_loc_delta": sum(item["estimated_loc_delta"] for item in items),
        "duplicate_abstractions": sum(
            1 for item in items if "duplicate" in item["rationale"]
        ),
        "requirements_preserved": not requirement_affected,
        "test_surface_preserved": not test_surface_affected,
        "must_keep_violation": must_keep_violation,
    }


def _looks_like_delete_candidate(line: str) -> bool:
    lowered = line.lower()
    return any(hint in lowered for hint in DELETE_HINTS)


def _delete_item_for_line(
    line: str,
    must_keep: Sequence[str],
    tests: Sequence[str],
) -> dict[str, Any]:
    requirement_affected = _matching_marker(line, must_keep)
    test_surface_affected = _matching_marker(line, tests)
    must_keep_violation = requirement_affected != "none" or test_surface_affected != "none"
    lowered = line.lower()
    duplicate_signal = "duplicate" in lowered or "over-abstract" in lowered
    severity = "watch" if must_keep_violation else "must-delete"
    rationale = (
        "watch required or tested behavior before deleting"
        if must_keep_violation
        else "duplicate or over-abstract code path"
        if duplicate_signal
        else "deterministic deletion hint"
    )
    return {
        "item": line[:120],
        "severity": severity,
        "rationale": rationale,
        "estimated_loc_delta": -1 if not must_keep_violation else 0,
        "requirement_affected": requirement_affected,
        "test_surface_affected": test_surface_affected,
        "must_keep_violation": must_keep_violation,
    }


def _matching_marker(line: str, markers: Sequence[str]) -> str:
    return next((marker for marker in markers if marker and marker in line), "none")
