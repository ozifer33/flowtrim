from __future__ import annotations

import os
from collections.abc import Callable

from .models import Lane


PRIMARY_METRICS: dict[Lane, str] = {
    Lane.REPO_CONTEXT: "files_and_tokens_read",
    Lane.COMMAND_OUTPUT: "output_tokens",
    Lane.CODE_GENERATION: "generated_tokens",
    Lane.LONG_CONTEXT: "input_tokens",
    Lane.EXACT_EVIDENCE: "raw_required",
}

TOKENIZER_ENV = "FLOWTRIM_TOKENIZER"
_UNRESOLVED = object()
_resolved_counter: object = _UNRESOLVED


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    counter = _token_counter()
    if counter is not None:
        return counter(text)
    return _heuristic_tokens(text)


def _heuristic_tokens(text: str) -> int:
    # ~4 chars per token holds for ASCII only. Thai/CJK text tokenizes closer
    # to one token per character, so counting it at chars/4 would understate
    # usage by 3-4x.
    if text.isascii():
        return (len(text) + 3) // 4
    non_ascii = sum(1 for character in text if ord(character) > 127)
    ascii_chars = len(text) - non_ascii
    return (ascii_chars + 3) // 4 + non_ascii


def _token_counter() -> Callable[[str], int] | None:
    global _resolved_counter
    if _resolved_counter is _UNRESOLVED:
        _resolved_counter = _resolve_token_counter(os.environ.get(TOKENIZER_ENV))
    return _resolved_counter  # type: ignore[return-value]


def _resolve_token_counter(name: str | None) -> Callable[[str], int] | None:
    if name != "tiktoken":
        return None
    try:
        import tiktoken  # type: ignore

        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None
    return lambda text: len(encoding.encode(text))


def _reset_token_counter_cache() -> None:
    global _resolved_counter
    _resolved_counter = _UNRESOLVED


def savings_ratio(baseline_tokens: int, candidate_tokens: int) -> float:
    if baseline_tokens <= 0:
        return 0.0
    return round((baseline_tokens - candidate_tokens) / baseline_tokens, 4)


def lane_primary_metric(lane: Lane) -> str:
    return PRIMARY_METRICS[lane]
