import json
import unittest
from pathlib import Path

from flowtrim.benchmark import (
    _candidate,
    _command_case,
    build_aql_vault_readonly_suite,
    build_report,
    build_synthetic_heavy_suite,
    load_fixture,
    report_to_json,
    run_suite,
)
from flowtrim.models import Lane
from flowtrim.privacy import scan_text


FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "fixtures"


class BenchmarkSuiteTest(unittest.TestCase):
    def test_fixtures_are_public_safe(self):
        findings = {}
        for path in FIXTURES_ROOT.rglob("*"):
            if path.is_file():
                hits = scan_text(path.read_text(errors="ignore"))
                if hits:
                    findings[path.relative_to(FIXTURES_ROOT).as_posix()] = hits

        self.assertEqual(findings, {})

    def test_load_fixture_reads_relative_to_fixture_root(self):
        text = load_fixture("exact/source-quote.txt", FIXTURES_ROOT)

        self.assertIn("quote-demo-001", text)

    def test_synthetic_suite_shape_and_outcomes(self):
        cases = build_synthetic_heavy_suite(FIXTURES_ROOT)
        lane_counts = {}
        for case in cases:
            lane_counts[case.lane] = lane_counts.get(case.lane, 0) + 1

        self.assertGreaterEqual(lane_counts[Lane.COMMAND_OUTPUT], 3)
        self.assertGreaterEqual(lane_counts[Lane.EXACT_EVIDENCE], 3)
        self.assertGreaterEqual(lane_counts[Lane.LONG_CONTEXT], 2)
        self.assertGreaterEqual(lane_counts[Lane.CODE_GENERATION], 2)
        self.assertIn("mutation/missing-path", {case.case_id for case in cases})
        self.assertIn("mutation/slower-candidate", {case.case_id for case in cases})
        self.assertIn("mutation/guard-failure", {case.case_id for case in cases})

        report = run_suite("synthetic-heavy", FIXTURES_ROOT)

        self.assertEqual(report.profile, "synthetic-heavy")
        self.assertGreaterEqual(report.metric_totals["token-bearing"]["wins"], 1)
        self.assertGreaterEqual(
            report.metric_totals["refusal-correctness"]["correct_refusals"],
            3,
        )
        self.assertGreaterEqual(report.metric_totals["code-lens"]["wins"], 2)
        self.assertGreaterEqual(report.metric_totals["token-bearing"]["skipped_methods"], 0)
        self.assertTrue(
            any(
                method.method == "headroom-direct" and method.status == "skipped"
                for case in report.cases
                for method in case.methods
            )
        )
        self.assertTrue(report.runtime_changes.is_none)

    def test_command_case_candidate_preservation_is_method_level(self):
        case = _command_case(
            "command-output/missing-candidate-path",
            "logs/noisy-build-fail.txt",
            FIXTURES_ROOT,
            candidates=[
                _candidate(
                    "flowtrim-selected",
                    Lane.COMMAND_OUTPUT,
                    "RetryBudgetExceeded compact summary",
                )
            ],
            must_preserve=("src/worker.py", "RetryBudgetExceeded"),
        )
        report = build_report("synthetic-heavy", [case], [], [])

        self.assertEqual(report.cases[0].winner, "insufficient-evidence")
        self.assertEqual(report.cases[0].selected_method, "raw")
        self.assertEqual(report.metric_totals["token-bearing"]["wins"], 0)

    def test_synthetic_report_json_is_privacy_safe(self):
        report = run_suite("synthetic-heavy", FIXTURES_ROOT)
        data = json.loads(report_to_json(report))

        self.assertEqual(data["schema"], "flowtrim-benchmark/v1")
        self.assertNotIn("/".join(("", "Users", "")), json.dumps(data))
        self.assertFalse(data["runtime_changes"]["installs"])
        self.assertFalse(data["runtime_changes"]["hooks"])
        self.assertFalse(data["runtime_changes"]["proxy"])
        self.assertFalse(data["runtime_changes"]["mcp"])

    def test_aql_vault_readonly_suite_shape_and_hybrid_verdict(self):
        cases = build_aql_vault_readonly_suite(FIXTURES_ROOT)

        self.assertEqual(len(cases), 6)
        self.assertTrue(all(case.runtime_changes.is_none for case in cases))

        report = run_suite("aql-vault-readonly", FIXTURES_ROOT)

        self.assertEqual(report.profile, "aql-vault-readonly")
        self.assertEqual(report.vault_verdict, "hybrid-only")
        self.assertEqual(len(report.cases), 6)
        self.assertTrue(report.runtime_changes.is_none)
        self.assertGreaterEqual(report.metric_totals["vault-semantic"]["atlas_deferrals"], 4)
        self.assertEqual(report.metric_totals["token-bearing"]["wins"], 0)

    def test_aql_vault_readonly_with_root_does_not_expose_root_path(self):
        report = run_suite(
            "aql-vault-readonly",
            FIXTURES_ROOT,
            aql_root=Path(__file__).resolve().parents[1],
        )
        data = json.loads(report_to_json(report))

        self.assertNotIn(str(Path(__file__).resolve().parents[1]), json.dumps(data))


if __name__ == "__main__":
    unittest.main()
