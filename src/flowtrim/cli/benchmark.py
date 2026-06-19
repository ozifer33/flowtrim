from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from flowtrim.benchmark import (
    DEFAULT_WORK_HISTORY_COMMIT_LIMIT,
    DEFAULT_WORK_HISTORY_FILES_PER_COMMIT,
    PUBLIC_PLAYGROUND_PROFILE,
    WORK_COMMIT_HISTORY_PROFILE,
    report_to_json,
    run_suite,
)
from flowtrim.compare import (
    compare_reports,
    compare_reports_to_json,
    compare_reports_to_markdown,
)
from flowtrim.docs_check import (
    docs_check_payload,
    docs_check_to_json,
    docs_check_to_markdown,
)
from flowtrim.doctor import doctor_payload, doctor_to_json, doctor_to_markdown
from flowtrim.metrics import estimate_tokens
from flowtrim.public_corpus import (
    DEFAULT_PUBLIC_CACHE_ROOT,
    DEFAULT_PUBLIC_CORPUS_MANIFEST,
    PUBLIC_OPEN_SOURCE_PROFILE,
    audit_public_corpus_manifest,
    prepare_public_corpus,
)
from flowtrim.release_checks import (
    claim_check_payload,
    evidence_from_flags,
    payload_to_json,
    payload_to_markdown,
    privacy_scan_payload,
    release_check_payload,
    tracked_paths,
)
from flowtrim.report_io import report_from_json_file
from flowtrim.skill_check import (
    skill_check_payload,
    skill_check_to_json,
    skill_check_to_markdown,
)


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
    if report.profile == WORK_COMMIT_HISTORY_PROFILE:
        lines.append("Sample: private local commit-history evidence only; aliases only.")
    if report.profile == PUBLIC_OPEN_SOURCE_PROFILE:
        lines.append("Sample: pinned public open-source corpus; aliases only.")
    if report.profile == PUBLIC_PLAYGROUND_PROFILE:
        lines.append("Sample: public-safe onboarding scenarios; no network or private data.")
    return "\n".join(lines)


def path_is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def repo_root() -> Path:
    return Path.cwd()


def report_write_blocker(reports_dir: Path, *, work_root: str | None, work_repos: list[str]) -> str | None:
    if reports_dir.resolve() == repo_root().resolve():
        return "reports-dir must not be inside repo-root"

    blocked_roots = [(Path.home() / "Documents" / "Work", "work-root")]
    if work_root:
        blocked_roots.append((Path(work_root), "work-root"))
    blocked_roots.extend((Path(work_repo), "work-repo") for work_repo in work_repos)

    for root, label in blocked_roots:
        if path_is_inside(reports_dir, root):
            return f"reports-dir must not be inside {label}"
    return None


def cache_root_blocker(cache_root: Path) -> str | None:
    if path_is_inside(cache_root, repo_root()):
        return "cache-root must not be inside repo-root"
    default_work = Path.home() / "Documents" / "Work"
    if path_is_inside(cache_root, default_work):
        return "cache-root must not be inside work-root"
    return None


def _public_corpus_audit_to_markdown(payload: dict) -> str:
    lines = [
        "# FlowTrim Public Corpus Audit",
        "",
        f"Valid: {payload['valid']}",
        f"Repos: {payload['repo_count']}",
        "Language families: " + ", ".join(payload["language_families"]),
        "Licenses: " + ", ".join(payload["licenses"]),
        f"Findings: {len(payload['findings'])}",
    ]
    lines.extend(f"- {item['target']}: {item['finding']}" for item in payload["findings"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["claim-check"]:
        parser = argparse.ArgumentParser(description="Validate a FlowTrim public claim.")
        parser.add_argument("command")
        parser.add_argument("--report", required=True)
        parser.add_argument("--claim", required=True)
        parser.add_argument("--format", choices=("json", "markdown"), default="json")
        args = parser.parse_args(argv)
        try:
            report = report_from_json_file(args.report)
        except ValueError as exc:
            parser.error(str(exc))
        payload = claim_check_payload(report, args.claim)
        output = (
            payload_to_json(payload) if args.format == "json" else payload_to_markdown(payload)
        )
        print(output)
        return 0 if payload["valid"] else 1

    if argv[:1] == ["privacy-scan"]:
        parser = argparse.ArgumentParser(description="Run a path-sanitized FlowTrim privacy scan.")
        parser.add_argument("command")
        parser.add_argument("--path", action="append", default=[])
        parser.add_argument("--tracked", action="store_true")
        parser.add_argument("--format", choices=("json", "markdown"), default="json")
        args = parser.parse_args(argv)
        paths = [Path(path) for path in args.path]
        if args.tracked:
            paths.extend(tracked_paths(Path.cwd()))
        if not paths:
            parser.error("privacy-scan requires --path or --tracked")
        payload = privacy_scan_payload(paths)
        output = (
            payload_to_json(payload) if args.format == "json" else payload_to_markdown(payload)
        )
        print(output)
        return 0 if not payload["findings"] else 1

    if argv[:1] == ["release-check"]:
        parser = argparse.ArgumentParser(description="Assess FlowTrim release readiness.")
        parser.add_argument("command")
        parser.add_argument("--report", required=True)
        parser.add_argument("--unit-tests-passed", action="store_true")
        parser.add_argument("--skill-validation-passed", action="store_true")
        parser.add_argument("--benchmark-smoke-passed", action="store_true")
        parser.add_argument("--privacy-scan-passed", action="store_true")
        parser.add_argument("--sanitized-report-present", action="store_true")
        parser.add_argument("--package-entrypoint-ready", action="store_true")
        parser.add_argument("--license-reviewed", action="store_true")
        parser.add_argument("--tool-versions-captured", action="store_true")
        parser.add_argument("--privacy-finding", action="append", default=[])
        parser.add_argument("--format", choices=("json", "markdown"), default="json")
        args = parser.parse_args(argv)
        try:
            report = report_from_json_file(args.report)
        except ValueError as exc:
            parser.error(str(exc))
        payload = release_check_payload(report, evidence_from_flags(args))
        output = (
            payload_to_json(payload) if args.format == "json" else payload_to_markdown(payload)
        )
        print(output)
        return 0 if payload["ready"] else 1

    if argv[:1] == ["skill-check"]:
        parser = argparse.ArgumentParser(description="Validate FlowTrim skill packaging shape.")
        parser.add_argument("command")
        parser.add_argument("--skill-root", required=True)
        parser.add_argument("--format", choices=("json", "markdown"), default="json")
        args = parser.parse_args(argv)
        payload = skill_check_payload(args.skill_root)
        output = (
            skill_check_to_json(payload)
            if args.format == "json"
            else skill_check_to_markdown(payload)
        )
        print(output)
        return 0 if payload["valid"] else 1

    if argv[:1] == ["docs-check"]:
        parser = argparse.ArgumentParser(description="Validate FlowTrim public documentation shape.")
        parser.add_argument("command")
        parser.add_argument("--root", default=".")
        parser.add_argument("--format", choices=("json", "markdown"), default="json")
        args = parser.parse_args(argv)
        payload = docs_check_payload(args.root)
        output = (
            docs_check_to_json(payload)
            if args.format == "json"
            else docs_check_to_markdown(payload)
        )
        print(output)
        return 0 if payload["valid"] else 1

    if argv[:1] == ["doctor"]:
        parser = argparse.ArgumentParser(description="Run aggregate FlowTrim public readiness checks.")
        parser.add_argument("command")
        parser.add_argument("--root", default=".")
        parser.add_argument("--skill-root", default="skills/flowtrim")
        parser.add_argument("--format", choices=("json", "markdown"), default="json")
        args = parser.parse_args(argv)
        payload = doctor_payload(args.root, skill_root=args.skill_root)
        output = (
            doctor_to_json(payload)
            if args.format == "json"
            else doctor_to_markdown(payload)
        )
        print(output)
        return 0 if payload["valid"] else 1

    if argv[:1] == ["compare"]:
        parser = argparse.ArgumentParser(description="Compare two FlowTrim benchmark reports.")
        parser.add_argument("command")
        parser.add_argument("--baseline-report", required=True)
        parser.add_argument("--candidate-report", required=True)
        parser.add_argument("--focus", default="headroom-direct")
        parser.add_argument("--format", choices=("json", "markdown"), default="json")
        args = parser.parse_args(argv)
        try:
            summary = compare_reports(
                args.baseline_report,
                args.candidate_report,
                focus=args.focus,
            )
        except ValueError as exc:
            parser.error(str(exc))
        output = (
            compare_reports_to_json(summary)
            if args.format == "json"
            else compare_reports_to_markdown(summary)
        )
        print(output)
        return 0

    if argv[:2] == ["public-corpus", "audit"]:
        parser = argparse.ArgumentParser(description="Audit pinned public corpus manifest quality.")
        parser.add_argument("public_corpus")
        parser.add_argument("command")
        parser.add_argument("--manifest", default=str(DEFAULT_PUBLIC_CORPUS_MANIFEST))
        parser.add_argument("--format", choices=("json", "markdown"), default="json")
        args = parser.parse_args(argv)
        payload = audit_public_corpus_manifest(args.manifest)
        output = (
            json.dumps(payload, indent=2, sort_keys=True)
            if args.format == "json"
            else _public_corpus_audit_to_markdown(payload)
        )
        print(output)
        return 0 if payload["valid"] else 1

    if argv[:2] == ["public-corpus", "prepare"]:
        parser = argparse.ArgumentParser(description="Prepare pinned public corpus cache.")
        parser.add_argument("public_corpus")
        parser.add_argument("command")
        parser.add_argument("--manifest", default=str(DEFAULT_PUBLIC_CORPUS_MANIFEST))
        parser.add_argument("--cache-root", default=str(DEFAULT_PUBLIC_CACHE_ROOT))
        parser.add_argument(
            "--source-override",
            nargs=2,
            action="append",
            default=[],
            metavar=("ALIAS", "SOURCE"),
            help=argparse.SUPPRESS,
        )
        args = parser.parse_args(argv)
        cache_root = Path(args.cache_root)
        blocker = cache_root_blocker(cache_root)
        if blocker:
            parser.error(blocker)
        result = prepare_public_corpus(
            args.manifest,
            cache_root,
            source_overrides=dict(args.source_override),
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if argv[:1] == ["suite"]:
        parser = argparse.ArgumentParser(description="Run a FlowTrim benchmark suite.")
        parser.add_argument("command")
        parser.add_argument(
            "--profile",
            choices=(
                "synthetic-heavy",
                "aql-vault-readonly",
                "work-code-readonly",
                WORK_COMMIT_HISTORY_PROFILE,
                PUBLIC_OPEN_SOURCE_PROFILE,
                PUBLIC_PLAYGROUND_PROFILE,
            ),
            required=True,
        )
        parser.add_argument("--format", choices=("json", "markdown"), default="json")
        parser.add_argument("--aql-root")
        parser.add_argument("--work-root")
        parser.add_argument("--work-repo", action="append", default=[])
        parser.add_argument("--public-corpus-manifest", default=str(DEFAULT_PUBLIC_CORPUS_MANIFEST))
        parser.add_argument("--public-cache-root", default=str(DEFAULT_PUBLIC_CACHE_ROOT))
        parser.add_argument("--headroom-executable")
        parser.add_argument("--repo-limit", type=int, default=9)
        parser.add_argument("--files-per-repo", type=int, default=12)
        parser.add_argument("--commit-limit", type=int, default=DEFAULT_WORK_HISTORY_COMMIT_LIMIT)
        parser.add_argument(
            "--files-per-commit",
            type=int,
            default=DEFAULT_WORK_HISTORY_FILES_PER_COMMIT,
        )
        parser.add_argument("--reports-dir", default="benchmarks/reports")
        parser.add_argument("--write-report", action="store_true")
        args = parser.parse_args(argv)

        if args.profile == WORK_COMMIT_HISTORY_PROFILE and not args.work_repo:
            parser.error("work-commit-history-readonly requires at least one --work-repo")

        report = run_suite(
            args.profile,
            aql_root=args.aql_root,
            work_root=args.work_root,
            work_repos=args.work_repo,
            public_corpus_manifest=args.public_corpus_manifest,
            public_cache_root=args.public_cache_root,
            repo_limit=args.repo_limit,
            files_per_repo=args.files_per_repo,
            commit_limit=args.commit_limit,
            files_per_commit=args.files_per_commit,
            headroom_executable=args.headroom_executable,
        )
        output = report_to_json(report) if args.format == "json" else report_to_markdown(report)
        if args.write_report:
            reports_dir = Path(args.reports_dir)
            blocker = report_write_blocker(
                reports_dir,
                work_root=args.work_root,
                work_repos=args.work_repo,
            )
            if blocker:
                parser.error(blocker)
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
