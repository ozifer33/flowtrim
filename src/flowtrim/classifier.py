from __future__ import annotations

import re

from .models import Lane


# ASCII entries match on word boundaries; non-ASCII entries (Thai) match as
# substrings because Thai text has no word separators.
COMMAND_WORDS = (
    "test",
    "build",
    "lint",
    "log",
    "grep",
    "search",
    "find",
    "npm",
    "pytest",
    "failed",
    "failing",
    "failure",
    "failures",
    "error",
    "errors",
    "output",
    "command",
    "compile",
    "เทสต์",
    "ทดสอบ",
    "บิลด์",
    "ล็อก",
    "รันคำสั่ง",
    "คอมไพล์",
    "พัง",
)
CODE_WORDS = (
    "write code",
    "refactor",
    "helper",
    "component",
    "abstraction",
    "function",
    "เขียนโค้ด",
    "รีแฟกเตอร์",
    "ฟังก์ชัน",
)
LONG_CONTEXT_WORDS = (
    "json",
    "trace",
    "payload",
    "handoff",
    "long context",
    "บริบทยาว",
    "แฮนด์ออฟ",
)
# Signals that the caller needs exact output. A task merely mentioning that
# something failed is a command-output signal, not an exact-evidence request.
EXACT_WORDS = (
    "exact",
    "diff",
    "line numbers",
    "line-level diff",
    "line level diff",
    "security",
    "short command",
    "source quote",
    "stack trace",
    "raw output",
    "verbatim",
    "ดิบ",
    "เป๊ะ",
    "ทุกบรรทัด",
    "สแตกเทรซ",
    "ตามต้นฉบับ",
)


def classify_text(text: str) -> tuple[Lane, ...]:
    lowered = text.lower()
    lanes: list[Lane] = []

    if _matches(lowered, EXACT_WORDS):
        lanes.append(Lane.EXACT_EVIDENCE)
    if _matches(lowered, COMMAND_WORDS):
        lanes.append(Lane.COMMAND_OUTPUT)
    if _matches(lowered, CODE_WORDS):
        lanes.append(Lane.CODE_GENERATION)
    if _matches(lowered, LONG_CONTEXT_WORDS):
        lanes.append(Lane.LONG_CONTEXT)
    if not lanes:
        lanes.append(Lane.REPO_CONTEXT)

    return tuple(dict.fromkeys(lanes))


def _matches(lowered: str, words: tuple[str, ...]) -> bool:
    return any(_word_pattern(word).search(lowered) for word in words)


_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


def _word_pattern(word: str) -> re.Pattern[str]:
    pattern = _PATTERN_CACHE.get(word)
    if pattern is None:
        escaped = re.escape(word)
        pattern = re.compile(rf"\b{escaped}\b" if word.isascii() else escaped)
        _PATTERN_CACHE[word] = pattern
    return pattern
