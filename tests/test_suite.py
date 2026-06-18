import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from flowtrim.benchmark import (
    _candidate,
    _command_case,
    _tool_infos,
    build_aql_vault_readonly_suite,
    build_report,
    build_synthetic_heavy_suite,
    build_work_code_readonly_suite,
    load_fixture,
    report_to_json,
    run_suite,
)
from flowtrim.models import Lane
from flowtrim.privacy import scan_text


FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "fixtures"


def create_work_repo(work_root: Path, repo_name: str = "repo-a") -> Path:
    repo = work_root / repo_name
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    source = repo / "src" / "feature.ts"
    source.parent.mkdir()
    source.write_text(
        "\n".join(
            [
                "export function veryUniquePrivateLogicName(input: string) {",
                "  const normalized = input.trim().toLowerCase();",
                "  const repeated = normalizeSharedValue(normalized);",
                "  const repeated = normalizeSharedValue(normalized);",
                "  const repeated = normalizeSharedValue(normalized);",
                "  return repeated;",
                "}",
                "export const wrapper = (value: string) => normalizeSharedValue(value);",
            ]
        ),
        encoding="utf-8",
    )
    return repo


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
        self.assertIn("long-context/marker-only-unsafe", {case.case_id for case in cases})

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

        marker_case = next(
            case for case in report.cases if case.case_id == "long-context/marker-only-unsafe"
        )
        self.assertEqual(marker_case.winner, "insufficient-evidence")
        self.assertEqual(marker_case.selected_method, "raw")

    def test_rtk_fixture_methods_are_marked_as_fixture_replay(self):
        report = run_suite("synthetic-heavy", FIXTURES_ROOT)
        rtk_methods = [
            method
            for case in report.cases
            for method in case.methods
            if method.method == "rtk"
        ]

        self.assertTrue(rtk_methods)
        self.assertTrue(
            all(method.reason == "fixture replay via injected safe runner" for method in rtk_methods)
        )

    def test_synthetic_noisy_command_cases_compare_native_against_rtk(self):
        report = run_suite("synthetic-heavy", FIXTURES_ROOT)
        noisy_cases = [
            case
            for case in report.cases
            if case.case_id
            in {
                "command-output/noisy-build-pass",
                "command-output/noisy-build-fail",
            }
        ]

        self.assertEqual(len(noisy_cases), 2)
        for case in noisy_cases:
            with self.subTest(case_id=case.case_id):
                methods = {method.method: method for method in case.methods}
                self.assertIn("raw", methods)
                self.assertIn("rtk", methods)
                self.assertIn("flowtrim-native-command", methods)
                self.assertEqual(case.selected_method, "flowtrim-native-command")
                self.assertLess(
                    methods["flowtrim-native-command"].tokens,
                    methods["rtk"].tokens,
                )
                self.assertTrue(methods["flowtrim-native-command"].guard_passed)
                self.assertIn("status", methods["flowtrim-native-command"].payload)
                self.assertIn("primary_files", methods["flowtrim-native-command"].payload)

    def test_tool_info_captures_version_for_available_tools(self):
        infos = _tool_infos(
            which=lambda name: "/tool/" + name if name == "rtk" else None,
            version_runner=lambda path: "rtk 1.2.3",
        )

        rtk = next(tool for tool in infos if tool.name == "rtk")
        headroom = next(tool for tool in infos if tool.name == "headroom")

        self.assertTrue(rtk.available)
        self.assertEqual(rtk.version, "rtk 1.2.3")
        self.assertFalse(headroom.available)

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

    def test_work_code_readonly_suite_uses_real_code_without_leaking_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            work_root = Path(tmpdir)
            create_work_repo(work_root)

            report = run_suite(
                "work-code-readonly",
                FIXTURES_ROOT,
                work_root=work_root,
                repo_limit=1,
                files_per_repo=2,
            )
            text = report_to_json(report)
            data = json.loads(text)

        self.assertEqual(data["profile"], "work-code-readonly")
        self.assertEqual(data["runtime_changes"]["unapproved_filesystem_writes"], False)
        self.assertGreaterEqual(data["metric_totals"]["code-lens"]["cases"], 1)
        self.assertGreaterEqual(data["metric_totals"]["code-lens"]["delete_items"], 1)
        self.assertNotIn(str(work_root), text)
        self.assertNotIn("veryUniquePrivateLogicName", text)
        self.assertNotIn("repo-a", text)
        self.assertNotIn("feature.ts", text)
        self.assertNotIn("normalizeSharedValue", text)
        self.assertNotIn("const repeated", text)
        self.assertIn("work-code/repo-01/file-01", {case["case_id"] for case in data["cases"]})

    def test_work_code_readonly_builder_limits_repos_and_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            work_root = Path(tmpdir)
            create_work_repo(work_root, "repo-a")
            create_work_repo(work_root, "repo-b")

            cases = build_work_code_readonly_suite(
                work_root,
                repo_limit=1,
                files_per_repo=1,
            )

        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].case_id, "work-code/repo-01/file-01")


if __name__ == "__main__":
    unittest.main()
