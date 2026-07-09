from __future__ import annotations

import argparse
import json
import subprocess
import sys

from flowtrim.models import Lane
from flowtrim.trim import (
    EXCERPT_FALLBACK,
    TrimDecision,
    excerpt_decision,
    raw_decision,
    trim_text,
)


RUN_SCHEMA = "flowtrim-run/v1"


def decision_to_json(decision: TrimDecision, exit_code: int) -> str:
    return json.dumps(
        {
            "schema": RUN_SCHEMA,
            "exit_code": exit_code,
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


def stats_line(decision: TrimDecision, exit_code: int) -> str:
    if decision.action in ("trimmed", "excerpt"):
        detail = (
            f"{decision.action} {decision.baseline_tokens} -> "
            f"{decision.output_tokens} tokens ({decision.savings * 100:.1f}% saved)"
        )
    else:
        detail = f"raw fallback: {decision.reason}"
    return f"flowtrim-run: exit {exit_code} | {detail}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a command and print token-reduced output. The command's exit code "
            "is the pass/fail ground truth and is propagated as this process's exit "
            "code. Passing runs are trimmed to a fact packet; failing runs keep a "
            "bounded excerpt with the error context by default."
        )
    )
    parser.add_argument(
        "--must-preserve",
        action="append",
        default=[],
        help="Fact that must survive verbatim in the output; repeatable.",
    )
    fail_group = parser.add_mutually_exclusive_group()
    fail_group.add_argument(
        "--raw-on-fail",
        action="store_true",
        help="Print full raw output when the command fails.",
    )
    fail_group.add_argument(
        "--trim-on-fail",
        action="store_true",
        help="Trim failing output to a fact packet instead of keeping an excerpt.",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the stats line printed to stderr in text mode.",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to run, after a -- separator.",
    )
    args = parser.parse_args(argv)

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a command is required after --")

    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    except (FileNotFoundError, PermissionError):
        parser.error("command executable could not be started")

    output = completed.stdout or ""
    exit_code = completed.returncode
    must_preserve = tuple(args.must_preserve)

    if exit_code == 0:
        decision = trim_text(
            output,
            must_preserve=must_preserve,
            lane=Lane.COMMAND_OUTPUT,
            fallback=EXCERPT_FALLBACK,
            status_override="pass",
        )
    elif args.raw_on_fail:
        decision = raw_decision(output, reason="raw output kept for failing command")
    elif args.trim_on_fail:
        decision = trim_text(
            output,
            must_preserve=must_preserve,
            lane=Lane.COMMAND_OUTPUT,
            fallback=EXCERPT_FALLBACK,
            status_override="fail",
        )
    else:
        decision = excerpt_decision(output, must_preserve=must_preserve)

    if args.format == "json":
        print(decision_to_json(decision, exit_code))
        return exit_code

    if decision.text:
        sys.stdout.write(
            decision.text if decision.text.endswith("\n") else decision.text + "\n"
        )
    if not args.quiet:
        print(stats_line(decision, exit_code), file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
