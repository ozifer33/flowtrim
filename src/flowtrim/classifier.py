from __future__ import annotations

from .models import Lane


COMMAND_WORDS = ("test", "build", "lint", "log", "grep", "search", "find", "npm", "pytest")
CODE_WORDS = ("write code", "refactor", "helper", "component", "abstraction", "function")
LONG_CONTEXT_WORDS = ("json", "trace", "payload", "handoff", "long context")
EXACT_WORDS = (
    "exact",
    "diff",
    "failed",
    "failure",
    "failures",
    "failing",
    "line numbers",
    "line-level diff",
    "line level diff",
    "security",
    "short command",
    "source quote",
    "stack trace",
)


def classify_text(text: str) -> tuple[Lane, ...]:
    lowered = text.lower()
    lanes: list[Lane] = []

    if any(word in lowered for word in EXACT_WORDS):
        lanes.append(Lane.EXACT_EVIDENCE)
    if any(word in lowered for word in COMMAND_WORDS):
        lanes.append(Lane.COMMAND_OUTPUT)
    if any(word in lowered for word in CODE_WORDS):
        lanes.append(Lane.CODE_GENERATION)
    if any(word in lowered for word in LONG_CONTEXT_WORDS):
        lanes.append(Lane.LONG_CONTEXT)
    if not lanes:
        lanes.append(Lane.REPO_CONTEXT)

    return tuple(dict.fromkeys(lanes))
