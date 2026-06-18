#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flowtrim.benchmark import report_to_json, run_suite
from flowtrim.metrics import estimate_tokens


def report_to_markdown(report) -> str:
    lines = [
        "# FlowTrim Benchmark Report",
        "",
        f"Profile: {report.profile}",
        f"Cases: {len(report.cases)}",
        f"Vault verdict: {report.vault_verdict}",
        f"Token wins: {report.metric_totals['token-bearing']['wins']}",
        f"Correct refusals: {report.metric_totals['refusal-correctness']['correct_refusals']}",
        f"Code-lens wins: {report.metric_totals['code-lens']['wins']}",
        f"Runtime changes: {'none' if report.runtime_changes.is_none else 'detected'}",
    ]
    if report.profile == "work-code-readonly":
        lines.append("Sample: high-signal files only; not an average prevalence estimate.")
    return "\n".join(lines)


def path_is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["suite"]:
        parser = argparse.ArgumentParser(description="Run a FlowTrim benchmark suite.")
        parser.add_argument("command")
        parser.add_argument(
            "--profile",
            choices=("synthetic-heavy", "aql-vault-readonly", "work-code-readonly"),
            required=True,
        )
        parser.add_argument("--format", choices=("json", "markdown"), default="json")
        parser.add_argument("--aql-root")
        parser.add_argument("--work-root")
        parser.add_argument("--repo-limit", type=int, default=9)
        parser.add_argument("--files-per-repo", type=int, default=12)
        parser.add_argument("--reports-dir", default="benchmarks/reports")
        parser.add_argument("--write-report", action="store_true")
        args = parser.parse_args(argv)

        report = run_suite(
            args.profile,
            aql_root=args.aql_root,
            work_root=args.work_root,
            repo_limit=args.repo_limit,
            files_per_repo=args.files_per_repo,
        )
        output = report_to_json(report) if args.format == "json" else report_to_markdown(report)
        if args.write_report:
            reports_dir = Path(args.reports_dir)
            if args.profile == "work-code-readonly":
                work_root = Path(args.work_root) if args.work_root else Path.home() / "Documents" / "Work"
                if path_is_inside(reports_dir, work_root):
                    parser.error("reports-dir must not be inside work-root")
            reports_dir.mkdir(parents=True, exist_ok=True)
            extension = "json" if args.format == "json" else "md"
            path = reports_dir / f"{args.profile}.{extension}"
            path.write_text(output + "\n", encoding="utf-8")
            print(f"report written: {path.name}")
        else:
            print(output)
        return 0

    parser = argparse.ArgumentParser(description="Estimate tokens for benchmark fixture text.")
    parser.add_argument("text", nargs="?", help="Text to estimate.")
    args = parser.parse_args(argv)
    if args.text is None:
        parser.error("text is required unless using the suite subcommand")

    print(estimate_tokens(args.text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
