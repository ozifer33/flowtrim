from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from flowtrim.models import Lane
from flowtrim.trim import (
    EXCERPT_FALLBACK,
    RAW_FALLBACK,
    TRIM_SCHEMA,
    TrimDecision,
    trim_text,
)


def decision_to_json(decision: TrimDecision) -> str:
    return json.dumps(
        {
            "schema": TRIM_SCHEMA,
            "action": decision.action,
            "lane": decision.lane.value,
            "baseline_tokens": decision.baseline_tokens,
            "output_tokens": decision.output_tokens,
            "savings_ratio": decision.savings,
            "reason": decision.reason,
            "text": decision.text,
            "payload": decision.payload,
        },
        indent=2,
        sort_keys=True,
    )


def decision_stats_line(decision: TrimDecision) -> str:
    if decision.action in ("trimmed", "excerpt"):
        return (
            f"flowtrim-trim: {decision.action} {decision.baseline_tokens} -> "
            f"{decision.output_tokens} tokens ({decision.savings * 100:.1f}% saved)"
        )
    return f"flowtrim-trim: raw fallback: {decision.reason}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Trim noisy command output into a fact-preserving packet. "
            "Falls back to raw output whenever a preservation or token gate fails."
        )
    )
    parser.add_argument("--file", help="Read input from this file instead of stdin.")
    parser.add_argument(
        "--must-preserve",
        action="append",
        default=[],
        help="Fact that must survive trimming verbatim; repeatable.",
    )
    parser.add_argument(
        "--lane",
        choices=tuple(lane.value for lane in Lane),
        help="Force a lane instead of classifying the task text.",
    )
    parser.add_argument(
        "--task",
        help="Task description used to classify the lane when --lane is absent.",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--fallback",
        choices=(RAW_FALLBACK, EXCERPT_FALLBACK),
        default=RAW_FALLBACK,
        help=(
            "What to emit when a trim gate fails: full raw output (default), or a "
            "bounded head/tail/error-window excerpt with omission markers."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the stats line printed to stderr in text mode.",
    )
    args = parser.parse_args(argv)

    if args.file is not None:
        try:
            text = Path(args.file).read_text(encoding="utf-8")
        except OSError:
            parser.error("input file is unreadable")
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        parser.error("text input is required via --file or stdin")

    decision = trim_text(
        text,
        must_preserve=tuple(args.must_preserve),
        lane=Lane(args.lane) if args.lane else None,
        task=args.task,
        fallback=args.fallback,
    )

    if args.format == "json":
        print(decision_to_json(decision))
        return 0

    sys.stdout.write(decision.text if decision.text.endswith("\n") else decision.text + "\n")
    if not args.quiet:
        print(decision_stats_line(decision), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
