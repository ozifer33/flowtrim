import unittest
from dataclasses import replace

from flowtrim.benchmark import ToolInfo
from flowtrim.benchmark import run_suite
from flowtrim.publication import (
    ReleaseEvidence,
    assess_release_readiness,
    validate_claim,
)


def complete_evidence(**overrides):
    evidence = ReleaseEvidence(
        unit_tests_passed=True,
        skill_validation_passed=True,
        benchmark_smoke_passed=True,
        privacy_scan_passed=True,
        sanitized_report_present=True,
        package_entrypoint_ready=True,
        license_reviewed=True,
        tool_versions_captured=True,
        privacy_findings=(),
    )
    return replace(evidence, **overrides)


class PublicationTest(unittest.TestCase):
    def test_release_is_blocked_when_required_evidence_is_missing(self):
        report = run_suite("synthetic-heavy")
        readiness = assess_release_readiness(
            report,
            complete_evidence(unit_tests_passed=False, skill_validation_passed=False),
        )

        self.assertFalse(readiness.ready)
        self.assertIn("unit tests have not passed", readiness.blockers)
        self.assertIn("skill validation has not passed", readiness.blockers)

    def test_privacy_findings_block_release(self):
        report = run_suite("synthetic-heavy")
        readiness = assess_release_readiness(
            report,
            complete_evidence(privacy_scan_passed=False, privacy_findings=("private-path",)),
        )

        self.assertFalse(readiness.ready)
        self.assertIn("privacy scan has not passed", readiness.blockers)
        self.assertIn("privacy findings: private-path", readiness.blockers)

    def test_package_entrypoint_gap_is_backlog_not_false_pass(self):
        report = run_suite("synthetic-heavy")
        readiness = assess_release_readiness(
            report,
            complete_evidence(package_entrypoint_ready=False),
        )

        self.assertTrue(readiness.ready)
        self.assertIn(
            "Add package entry points or document PYTHONPATH=src limitation.",
            readiness.backlog,
        )

    def test_available_tool_without_version_blocks_release_even_if_evidence_claims_ready(self):
        report = run_suite("synthetic-heavy")
        report = replace(
            report,
            tools=[
                ToolInfo(name="rtk", available=True, version=None),
                ToolInfo(name="headroom", available=False, reason="not installed"),
            ],
        )

        readiness = assess_release_readiness(
            report,
            complete_evidence(tool_versions_captured=True),
        )

        self.assertFalse(readiness.ready)
        self.assertIn("available tool version missing: rtk", readiness.blockers)

    def test_hybrid_vault_verdict_is_preserved(self):
        report = run_suite("aql-vault-readonly")
        readiness = assess_release_readiness(report, complete_evidence())

        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.vault_verdict, "hybrid-only")
        self.assertNotIn("FlowTrim is vault-safe.", readiness.allowed_claims)

    def test_claim_validation_is_lane_specific_and_blocks_global_overclaims(self):
        synthetic = run_suite("synthetic-heavy")
        vault = run_suite("aql-vault-readonly")

        self.assertTrue(
            validate_claim(
                synthetic,
                "FlowTrim selected a safe lower-token method for this measured lane.",
            )
        )
        self.assertTrue(
            validate_claim(
                synthetic,
                "FlowTrim correctly chose raw because compression was unsafe or not cheaper.",
            )
        )
        self.assertFalse(validate_claim(synthetic, "FlowTrim beats RTK, Ponytail, and Headroom globally."))
        self.assertFalse(validate_claim(synthetic, "Headroom lost to FlowTrim."))
        self.assertFalse(validate_claim(synthetic, "Ponytail saved tokens."))
        self.assertFalse(validate_claim(vault, "FlowTrim is vault-safe."))


if __name__ == "__main__":
    unittest.main()
