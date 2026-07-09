from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .adapters import hash_text
from .classifier import classify_text
from .metrics import estimate_tokens, savings_ratio
from .models import Lane
from .native_command import (
    ERROR_LINE_RE,
    ERROR_RE,
    compact_command_output,
    _file_paths,
    _omitted_noise_classes,
)
from .preservation import check_preservation


TRIM_SCHEMA = "flowtrim-trim/v1"
TRIMMABLE_LANES = (Lane.COMMAND_OUTPUT, Lane.LONG_CONTEXT)
RAW_FALLBACK = "raw"
EXCERPT_FALLBACK = "excerpt"

HYPHEN_ID_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*-\d+\b")
PREFIXED_ID_RE = re.compile(
    r"\b(?:source|trace|job|req|requirement|run|ticket|span)[:=][A-Za-z0-9._/-]+",
    re.IGNORECASE,
)
UPPER_ERROR_RE = re.compile(r"\b[A-Z][A-Z0-9_]*(?:ERROR|FAILURE|EXCEPTION)\b")
MAX_IDS = 8
MAX_FILES = 5
MAX_ERRORS = 5
EXCERPT_HEAD_LINES = 12
EXCERPT_TAIL_LINES = 8
EXCERPT_CONTEXT_LINES = 2


@dataclass(frozen=True)
class TrimDecision:
    action: str
    lane: Lane
    text: str
    baseline_tokens: int
    output_tokens: int
    reason: str
    payload: dict[str, Any]

    @property
    def trimmed(self) -> bool:
        return self.action == "trimmed"

    @property
    def savings(self) -> float:
        return savings_ratio(self.baseline_tokens, self.output_tokens)


def resolve_lane(*, lane: Lane | None = None, task: str | None = None) -> Lane:
    if lane is not None:
        return lane
    if task:
        return classify_text(task)[0]
    return Lane.COMMAND_OUTPUT


def trim_text(
    text: str,
    *,
    must_preserve: tuple[str, ...] = (),
    lane: Lane | None = None,
    task: str | None = None,
    fallback: str = RAW_FALLBACK,
    status_override: str | None = None,
) -> TrimDecision:
    resolved_lane = resolve_lane(lane=lane, task=task)
    baseline_tokens = estimate_tokens(text)

    if resolved_lane not in TRIMMABLE_LANES:
        return _raw_decision(
            text,
            resolved_lane,
            baseline_tokens,
            reason=f"lane {resolved_lane.value} requires raw output",
        )

    if resolved_lane == Lane.LONG_CONTEXT:
        packet_text, payload = _long_context_packet(text, must_preserve)
    else:
        packet = compact_command_output(
            text,
            must_preserve=must_preserve,
            status_override=status_override,
        )
        packet_text, payload = packet.text, packet.payload

    gate_failure = _gate_failure(text, packet_text, must_preserve, baseline_tokens)
    if gate_failure is None and not _packet_has_facts(payload, text, must_preserve):
        gate_failure = "packet has no extractable facts"
    if gate_failure is None:
        return TrimDecision(
            action="trimmed",
            lane=resolved_lane,
            text=packet_text,
            baseline_tokens=baseline_tokens,
            output_tokens=estimate_tokens(packet_text),
            reason="preservation and token gates passed",
            payload=payload,
        )

    if fallback == EXCERPT_FALLBACK:
        excerpt = _excerpt_text(text, must_preserve)
        if _gate_failure(text, excerpt, must_preserve, baseline_tokens) is None:
            return TrimDecision(
                action="excerpt",
                lane=resolved_lane,
                text=excerpt,
                baseline_tokens=baseline_tokens,
                output_tokens=estimate_tokens(excerpt),
                reason=f"packet rejected ({gate_failure}); bounded excerpt kept",
                payload={"content_hash": hash_text(text)},
            )

    return _raw_decision(text, resolved_lane, baseline_tokens, reason=gate_failure)


def excerpt_decision(
    text: str,
    *,
    must_preserve: tuple[str, ...] = (),
    lane: Lane = Lane.COMMAND_OUTPUT,
) -> TrimDecision:
    baseline_tokens = estimate_tokens(text)
    excerpt = _excerpt_text(text, must_preserve)
    failure = _gate_failure(text, excerpt, must_preserve, baseline_tokens)
    if failure is not None:
        return _raw_decision(text, lane, baseline_tokens, reason=failure)
    return TrimDecision(
        action="excerpt",
        lane=lane,
        text=excerpt,
        baseline_tokens=baseline_tokens,
        output_tokens=estimate_tokens(excerpt),
        reason="bounded excerpt kept",
        payload={"content_hash": hash_text(text)},
    )


def raw_decision(
    text: str,
    *,
    lane: Lane = Lane.COMMAND_OUTPUT,
    reason: str = "raw output requested",
) -> TrimDecision:
    return _raw_decision(text, lane, estimate_tokens(text), reason=reason)


def _packet_has_facts(
    payload: dict[str, Any],
    text: str,
    must_preserve: tuple[str, ...],
) -> bool:
    if any(item and item in text for item in must_preserve):
        return True
    if payload.get("status") in ("pass", "fail", "warning"):
        return True
    fact_keys = (
        "failing_tests",
        "error_labels",
        "error_lines",
        "summary_lines",
        "primary_files",
        "source_ids",
    )
    return any(payload.get(key) for key in fact_keys)


def _gate_failure(
    text: str,
    candidate: str,
    must_preserve: tuple[str, ...],
    baseline_tokens: int,
) -> str | None:
    preservation = check_preservation(text, candidate, must_preserve)
    if not preservation.passed:
        return preservation.reason
    if estimate_tokens(candidate) >= baseline_tokens:
        return "no token savings over raw output"
    return None


def _raw_decision(
    text: str,
    lane: Lane,
    baseline_tokens: int,
    *,
    reason: str,
) -> TrimDecision:
    return TrimDecision(
        action="raw",
        lane=lane,
        text=text,
        baseline_tokens=baseline_tokens,
        output_tokens=baseline_tokens,
        reason=reason,
        payload={},
    )


def _long_context_packet(
    text: str,
    must_preserve: tuple[str, ...],
) -> tuple[str, dict[str, Any]]:
    ids = _unique([*PREFIXED_ID_RE.findall(text), *HYPHEN_ID_RE.findall(text)])[:MAX_IDS]
    files = _file_paths(text)[:MAX_FILES]
    errors = _unique([*ERROR_RE.findall(text), *UPPER_ERROR_RE.findall(text)])[:MAX_ERRORS]
    stripped_lines = [line.strip() for line in text.splitlines() if line.strip()]

    lines = []
    if ids:
        lines.append("ids: " + ", ".join(ids))
    if files:
        lines.append("files: " + ", ".join(files))
    if errors:
        lines.append("errors: " + ", ".join(errors))
    present_items = [item for item in must_preserve if item and item in text]
    missing_from_packet = [
        item for item in present_items if not any(item in line for line in lines)
    ]
    if missing_from_packet:
        lines.append("must-keep: " + ", ".join(dict.fromkeys(missing_from_packet)))
    omitted = _omitted_noise_classes(stripped_lines)
    if omitted:
        lines.append("omitted: " + ", ".join(omitted))
    content_hash = hash_text(text)
    lines.append(f"raw-hash: {content_hash}")
    packet_text = "\n".join(lines)
    payload = {
        "content_hash": content_hash,
        "source_ids": ids,
        "primary_files": files,
        "error_labels": errors,
        "must_keep": list(must_preserve),
        "omitted_noise_classes": omitted,
        "sanitized_snippet": packet_text,
    }
    return packet_text, payload


def _excerpt_text(text: str, must_preserve: tuple[str, ...]) -> str:
    lines = text.splitlines()
    if not lines:
        return text
    keep: set[int] = set(range(min(EXCERPT_HEAD_LINES, len(lines))))
    keep.update(range(max(len(lines) - EXCERPT_TAIL_LINES, 0), len(lines)))
    for index, line in enumerate(lines):
        interesting = (
            ERROR_LINE_RE.search(line)
            or line.strip().upper().endswith(" FAILED")
            or any(item and item in line for item in must_preserve)
        )
        if interesting:
            start = max(index - EXCERPT_CONTEXT_LINES, 0)
            end = min(index + EXCERPT_CONTEXT_LINES + 1, len(lines))
            keep.update(range(start, end))

    output: list[str] = []
    previous = -1
    for index in sorted(keep):
        if previous >= 0 and index > previous + 1:
            output.append(f"[flowtrim: omitted {index - previous - 1} lines]")
        output.append(lines[index])
        previous = index
    return "\n".join(output)


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
