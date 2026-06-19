import json
import unittest
from dataclasses import replace

from flowtrim.benchmark import (
    BenchmarkStatus,
    MetricFamily,
    report_to_json,
    run_suite,
)
from flowtrim.models import Lane
from flowtrim.report_io import report_from_json


class ReportIoTest(unittest.TestCase):
    def test_report_from_json_round_trips_report_dataclasses(self):
        original = run_suite("synthetic-heavy")
        parsed = report_from_json(report_to_json(original))

        self.assertEqual(parsed.schema, original.schema)
        self.assertEqual(parsed.profile, "synthetic-heavy")
        self.assertEqual(parsed.vault_verdict, original.vault_verdict)
        self.assertEqual(parsed.metric_totals, original.metric_totals)
        self.assertEqual(parsed.runtime_changes, original.runtime_changes)
        self.assertEqual(len(parsed.tools), len(original.tools))
        self.assertEqual(len(parsed.cases), len(original.cases))
        self.assertIs(parsed.cases[0].lane, Lane.COMMAND_OUTPUT)
        self.assertIs(parsed.cases[0].metric_family, MetricFamily.TOKEN_BEARING)
        self.assertIs(parsed.cases[0].methods[0].status, BenchmarkStatus.SELECTED)

    def test_report_from_json_rejects_non_benchmark_schema(self):
        payload = json.dumps({"schema": "other", "cases": []})

        with self.assertRaisesRegex(ValueError, "schema mismatch"):
            report_from_json(payload)

    def test_report_verification_evidence_round_trips_as_aggregate_only(self):
        original = run_suite("synthetic-heavy")
        report = replace(
            original,
            verification=[
                {
                    "command_alias": "backend-jest-full",
                    "status": "passed",
                    "suite_count": 30,
                    "test_count": 359,
                    "duration_bucket": "under-30s",
                },
                {
                    "command_alias": "referral-type-check",
                    "status": "blocked",
                    "blocker_reason": "external-project-type-errors",
                },
            ],
        )

        text = report_to_json(report)
        data = json.loads(text)
        parsed = report_from_json(text)

        self.assertEqual(data["verification"][0]["command_alias"], "backend-jest-full")
        self.assertEqual(data["verification"][1]["status"], "blocked")
        self.assertEqual(parsed.verification, report.verification)
        self.assertNotIn("src/pages", text)
        self.assertNotIn("playwright.config.ts", text)

    def test_report_verification_evidence_rejects_private_or_raw_log_text(self):
        original = run_suite("synthetic-heavy")
        private_path = (
            "/" + "Users" + "/example/"
            + "Documents" + "/" + "Work"
            + "/private-repo/src/file.ts"
        )
        report = replace(
            original,
            verification=[
                {
                    "command_alias": "unsafe-log",
                    "status": "failed",
                    "blocker_reason": private_path,
                }
            ],
        )

        with self.assertRaisesRegex(ValueError, "unsafe verification"):
            report_to_json(report)


if __name__ == "__main__":
    unittest.main()
