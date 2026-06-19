from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .benchmark import PUBLIC_PLAYGROUND_PROFILE, BenchmarkReport, run_suite
from .classifier import classify_text
from .docs_check import docs_check_payload
from .metrics import estimate_tokens
from .models import Lane
from .public_corpus import DEFAULT_PUBLIC_CORPUS_MANIFEST, audit_public_corpus_manifest
from .release_checks import package_metadata_findings, privacy_scan_payload, tracked_paths
from .skill_check import skill_check_payload


DOCTOR_SCHEMA = "flowtrim-doctor/v1"


def doctor_payload(
    root: str | Path = ".",
    *,
    skill_root: str | Path = "skills/flowtrim",
    tracked_path_loader: Callable[[Path], list[Path]] = tracked_paths,
) -> dict[str, Any]:
    repo_root = Path(root)
    checks = [
        _package_metadata_check(repo_root),
        _benchmark_smoke_check(),
        _classify_smoke_check(),
        _docs_check(repo_root),
        _skill_check(repo_root, skill_root),
        _privacy_check(repo_root, tracked_path_loader),
        _public_corpus_audit_check(repo_root),
        _public_playground_check(),
    ]
    return {
        "schema": DOCTOR_SCHEMA,
        "valid": all(check["valid"] for check in checks),
        "checks": checks,
    }


def doctor_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def doctor_to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# FlowTrim Doctor",
        "",
        f"Valid: {payload['valid']}",
        "",
        "## Checks",
    ]
    for check in payload["checks"]:
        status = "pass" if check["valid"] else "fail"
        lines.append(f"- {check['name']}: {status} ({check['summary']})")
    return "\n".join(lines)


def _check(name: str, valid: bool, summary: str) -> dict[str, Any]:
    return {"name": name, "valid": bool(valid), "summary": summary}


def _package_metadata_check(repo_root: Path) -> dict[str, Any]:
    findings = package_metadata_findings(repo_root)
    return _check(
        "package-metadata",
        not findings,
        "pyproject public package metadata and console scripts configured"
        if not findings
        else f"{len(findings)} metadata finding(s)",
    )


def _benchmark_smoke_check() -> dict[str, Any]:
    return _check(
        "benchmark-smoke",
        estimate_tokens("abcd") == 1,
        "abcd token estimate is 1",
    )


def _classify_smoke_check() -> dict[str, Any]:
    lanes = classify_text("npm test produced a long build log")
    return _check(
        "classify-smoke",
        lanes == (Lane.COMMAND_OUTPUT,),
        "npm build log classifies as command-output",
    )


def _docs_check(repo_root: Path) -> dict[str, Any]:
    payload = docs_check_payload(repo_root)
    return _check(
        "docs-check",
        payload["valid"],
        "public docs pass command and privacy rules"
        if payload["valid"]
        else f"{len(payload['findings'])} docs finding(s)",
    )


def _skill_check(repo_root: Path, skill_root: str | Path) -> dict[str, Any]:
    root = Path(skill_root)
    if not root.is_absolute():
        root = repo_root / root
    payload = skill_check_payload(root)
    return _check(
        "skill-check",
        payload["valid"],
        "skill shape and docs are valid"
        if payload["valid"]
        else f"{len(payload['findings'])} skill finding(s)",
    )


def _privacy_check(
    repo_root: Path,
    tracked_path_loader: Callable[[Path], list[Path]],
) -> dict[str, Any]:
    try:
        paths = tracked_path_loader(repo_root)
    except Exception:
        return _check("privacy-scan", False, "tracked files unavailable")
    payload = privacy_scan_payload(paths)
    return _check(
        "privacy-scan",
        not payload["findings"],
        f"{payload['files_scanned']} tracked text file(s), 0 findings"
        if not payload["findings"]
        else f"{len(payload['findings'])} privacy finding(s)",
    )


def _public_corpus_audit_check(repo_root: Path) -> dict[str, Any]:
    manifest = repo_root / "benchmarks" / "public-corpus" / "manifest.v1.json"
    if not manifest.exists():
        manifest = DEFAULT_PUBLIC_CORPUS_MANIFEST
    payload = audit_public_corpus_manifest(manifest)
    return _check(
        "public-corpus-audit",
        payload["valid"],
        f"{payload['repo_count']} pinned public repo(s), {len(payload['language_families'])} language family group(s)"
        if payload["valid"]
        else f"{len(payload['findings'])} corpus finding(s)",
    )


def _public_playground_check() -> dict[str, Any]:
    try:
        report = run_suite(PUBLIC_PLAYGROUND_PROFILE)
    except Exception:
        return _check("public-playground", False, "public playground suite failed")
    valid = _public_playground_is_useful(report)
    return _check(
        "public-playground",
        valid,
        (
            f"{len(report.cases)} scenario(s), "
            f"{report.metric_totals['token-bearing']['wins']} token win(s), "
            f"{report.metric_totals['refusal-correctness']['correct_refusals']} exact refusal(s), "
            f"{report.metric_totals['code-lens']['wins']} code-lens win(s)"
        ),
    )


def _public_playground_is_useful(report: BenchmarkReport) -> bool:
    return (
        report.schema == "flowtrim-benchmark/v1"
        and report.profile == PUBLIC_PLAYGROUND_PROFILE
        and report.runtime_changes.is_none
        and report.metric_totals["token-bearing"]["wins"] >= 1
        and report.metric_totals["refusal-correctness"]["correct_refusals"] >= 1
        and report.metric_totals["code-lens"]["wins"] >= 1
    )
