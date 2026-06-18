from __future__ import annotations

from dataclasses import dataclass, field

from .benchmark import BenchmarkReport, RuntimeChanges


FORBIDDEN_CLAIMS = (
    "FlowTrim beats RTK, Ponytail, and Headroom globally.",
    "Headroom lost to FlowTrim.",
    "Ponytail saved tokens.",
    "FlowTrim is vault-safe.",
)


@dataclass(frozen=True)
class ReleaseEvidence:
    unit_tests_passed: bool
    skill_validation_passed: bool
    benchmark_smoke_passed: bool
    privacy_scan_passed: bool
    sanitized_report_present: bool
    package_entrypoint_ready: bool
    license_reviewed: bool
    tool_versions_captured: bool
    privacy_findings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ReleaseReadiness:
    ready: bool
    blockers: list[str]
    backlog: list[str]
    allowed_claims: list[str]
    forbidden_claims: list[str]
    vault_verdict: str


def assess_release_readiness(
    report: BenchmarkReport,
    evidence: ReleaseEvidence,
) -> ReleaseReadiness:
    blockers = _evidence_blockers(evidence)
    if not report.runtime_changes.is_none:
        blockers.append("benchmark report recorded runtime changes")
    for tool in report.tools:
        if tool.available and not tool.version:
            blockers.append(f"available tool version missing: {tool.name}")

    backlog = list(report.upgrade_backlog)
    if not evidence.package_entrypoint_ready:
        backlog.append("Add package entry points or document PYTHONPATH=src limitation.")
    if any(tool.name == "headroom" and not tool.available for tool in report.tools):
        backlog.append("Document Headroom unavailable behavior and keep claims limited.")

    return ReleaseReadiness(
        ready=not blockers,
        blockers=blockers,
        backlog=_dedupe(backlog),
        allowed_claims=_allowed_claims(report),
        forbidden_claims=list(FORBIDDEN_CLAIMS),
        vault_verdict=report.vault_verdict,
    )


def validate_claim(report: BenchmarkReport, claim: str) -> bool:
    normalized = " ".join(claim.lower().split())
    if _is_forbidden_claim(report, normalized):
        return False

    if "safe lower-token method" in normalized:
        return report.metric_totals["token-bearing"]["wins"] > 0
    if "correctly chose raw" in normalized:
        return any(case.selected_method == "raw" for case in report.cases)
    if "headroom was skipped" in normalized:
        return any(
            method.method == "headroom-direct" and method.status == "skipped"
            for case in report.cases
            for method in case.methods
        )
    if "ponytail lens reduced code complexity" in normalized:
        return report.metric_totals["code-lens"]["wins"] > 0
    if "hybrid-only" in normalized:
        return report.vault_verdict == "hybrid-only"

    return False


def _evidence_blockers(evidence: ReleaseEvidence) -> list[str]:
    blockers = []
    if not evidence.unit_tests_passed:
        blockers.append("unit tests have not passed")
    if not evidence.skill_validation_passed:
        blockers.append("skill validation has not passed")
    if not evidence.benchmark_smoke_passed:
        blockers.append("benchmark smoke has not passed")
    if not evidence.privacy_scan_passed:
        blockers.append("privacy scan has not passed")
    if evidence.privacy_findings:
        blockers.append("privacy findings: " + ", ".join(evidence.privacy_findings))
    if not evidence.sanitized_report_present:
        blockers.append("sanitized report is missing")
    if not evidence.license_reviewed:
        blockers.append("license and author metadata have not been reviewed")
    if not evidence.tool_versions_captured:
        blockers.append("tool availability or version evidence is missing")
    return blockers


def _allowed_claims(report: BenchmarkReport) -> list[str]:
    claims = []
    if report.metric_totals["token-bearing"]["wins"] > 0:
        claims.append("FlowTrim selected a safe lower-token method for this measured lane.")
    if any(case.selected_method == "raw" for case in report.cases):
        claims.append("FlowTrim correctly chose raw because compression was unsafe or not cheaper.")
    if any(
        method.method == "headroom-direct" and method.status == "skipped"
        for case in report.cases
        for method in case.methods
    ):
        claims.append("Headroom was skipped because it was unavailable.")
    if report.metric_totals["code-lens"]["wins"] > 0:
        claims.append(
            "Ponytail lens reduced code complexity without claiming direct token compression."
        )
    if report.vault_verdict == "hybrid-only":
        claims.append("Vault verdict is hybrid-only; Atlas context economy remains default.")
    if report.vault_verdict == "vault-safe":
        claims.append("Vault-safe is supported only for the measured read-only suite.")
    return claims


def _is_forbidden_claim(report: BenchmarkReport, normalized_claim: str) -> bool:
    if "beats rtk" in normalized_claim and "headroom" in normalized_claim and "globally" in normalized_claim:
        return True
    if "headroom lost" in normalized_claim:
        return True
    if "ponytail saved tokens" in normalized_claim:
        return True
    if "vault-safe" in normalized_claim or "vault safe" in normalized_claim:
        return report.vault_verdict != "vault-safe"
    return False


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
