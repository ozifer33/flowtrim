import json
import unittest

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


if __name__ == "__main__":
    unittest.main()
