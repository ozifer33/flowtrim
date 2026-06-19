from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from .benchmark import BenchmarkReport
from .privacy import scan_text
from .publication import ReleaseEvidence, ReleaseReadiness, assess_release_readiness, validate_claim


CLAIM_CHECK_SCHEMA = "flowtrim-claim-check/v1"
PRIVACY_SCAN_SCHEMA = "flowtrim-privacy-scan/v1"
RELEASE_CHECK_SCHEMA = "flowtrim-release-check/v1"


def claim_check_payload(report: BenchmarkReport, claim: str) -> dict[str, Any]:
    valid = validate_claim(report, claim)
    return {
        "schema": CLAIM_CHECK_SCHEMA,
        "valid": valid,
        "claim_scope": "allowed" if valid else "rejected",
    }


def privacy_scan_payload(paths: list[Path]) -> dict[str, Any]:
    findings = []
    files_scanned = 0
    for index, path in enumerate(paths, start=1):
        target = f"input-{index:03d}"
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        except OSError:
            findings.append({"target": target, "finding": "unreadable"})
            continue
        files_scanned += 1
        for finding in scan_text(text):
            findings.append({"target": target, "finding": finding})
    return {
        "schema": PRIVACY_SCAN_SCHEMA,
        "files_scanned": files_scanned,
        "findings": findings,
    }


def tracked_paths(cwd: Path) -> list[Path]:
    output = subprocess.check_output(["git", "ls-files"], cwd=cwd, text=True)
    return [cwd / line for line in output.splitlines() if line]


def release_check_payload(
    report: BenchmarkReport,
    evidence: ReleaseEvidence,
) -> dict[str, Any]:
    readiness = assess_release_readiness(report, evidence)
    payload = release_readiness_payload(readiness)
    metadata_findings = package_metadata_findings(Path.cwd())
    payload["package_metadata"] = {
        "checked": True,
        "valid": not metadata_findings,
        "findings": metadata_findings,
    }
    if metadata_findings:
        payload["ready"] = False
        payload["blockers"].extend(
            f"package metadata: {finding}" for finding in metadata_findings
        )
    return payload


def package_metadata_findings(root: Path) -> list[str]:
    pyproject = root / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return ["pyproject metadata is unreadable"]

    project = data.get("project", {})
    findings = []
    required_project_keys = ("license", "requires-python", "keywords", "classifiers", "urls")
    for key in required_project_keys:
        if not project.get(key):
            findings.append(f"missing project.{key}")

    urls = project.get("urls", {})
    for key in ("Homepage", "Repository", "Issue Tracker"):
        if not urls.get(key):
            findings.append(f"missing project.urls.{key}")

    scripts = project.get("scripts", {})
    for key in ("flowtrim-benchmark", "flowtrim-classify"):
        if not scripts.get(key):
            findings.append(f"missing project.scripts.{key}")

    classifiers = project.get("classifiers", [])
    if not any("Programming Language :: Python :: 3.11" == value for value in classifiers):
        findings.append("missing Python 3.11 classifier")
    if not any("Programming Language :: Python :: 3.12" == value for value in classifiers):
        findings.append("missing Python 3.12 classifier")

    return findings


def release_readiness_payload(readiness: ReleaseReadiness) -> dict[str, Any]:
    return {
        "schema": RELEASE_CHECK_SCHEMA,
        "ready": readiness.ready,
        "blockers": readiness.blockers,
        "backlog": readiness.backlog,
        "allowed_claims": readiness.allowed_claims,
        "forbidden_claims": readiness.forbidden_claims,
        "vault_verdict": readiness.vault_verdict,
    }


def payload_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def payload_to_markdown(payload: dict[str, Any]) -> str:
    schema = payload.get("schema", "")
    lines = ["# FlowTrim Gate", "", f"Schema: {schema}"]
    if schema == CLAIM_CHECK_SCHEMA:
        lines.extend(
            [
                f"Valid: {payload['valid']}",
                f"Claim scope: {payload['claim_scope']}",
            ]
        )
    elif schema == PRIVACY_SCAN_SCHEMA:
        lines.extend(
            [
                f"Files scanned: {payload['files_scanned']}",
                f"Findings: {len(payload['findings'])}",
            ]
        )
    elif schema == RELEASE_CHECK_SCHEMA:
        lines.extend(
            [
                f"Ready: {payload['ready']}",
                f"Vault verdict: {payload['vault_verdict']}",
                f"Package metadata valid: {payload.get('package_metadata', {}).get('valid', False)}",
                "",
                "## Blockers",
                *[f"- {item}" for item in payload["blockers"]],
                "",
                "## Backlog",
                *[f"- {item}" for item in payload["backlog"]],
            ]
        )
    return "\n".join(lines)


def evidence_from_flags(args: Any) -> ReleaseEvidence:
    return ReleaseEvidence(
        unit_tests_passed=bool(args.unit_tests_passed),
        skill_validation_passed=bool(args.skill_validation_passed),
        benchmark_smoke_passed=bool(args.benchmark_smoke_passed),
        privacy_scan_passed=bool(args.privacy_scan_passed),
        sanitized_report_present=bool(args.sanitized_report_present),
        package_entrypoint_ready=bool(args.package_entrypoint_ready),
        license_reviewed=bool(args.license_reviewed),
        tool_versions_captured=bool(args.tool_versions_captured),
        privacy_findings=tuple(args.privacy_finding),
    )
