import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from flowtrim.benchmark import build_work_code_readonly_suite, report_to_json, run_suite
from flowtrim.privacy import scan_text
from flowtrim.publication import validate_claim


ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = ROOT / "benchmarks" / "fixtures"


SYNTHETIC_EXPECTATIONS = {
    "command-output/short-empty": ("raw", "raw", "raw-short-output", False),
    "command-output/noisy-build-pass": (
        "flowtrim-native-command",
        "flowtrim-native-command",
        "lower-token-safe",
        True,
    ),
    "command-output/noisy-build-fail": (
        "flowtrim-native-command",
        "flowtrim-native-command",
        "lower-token-safe",
        True,
    ),
    "exact-evidence/source-quote": ("raw", "raw", "correct-refusal", False),
    "exact-evidence/failing-stack-trace": ("raw", "raw", "correct-refusal", False),
    "exact-evidence/line-level-diff": ("raw", "raw", "correct-refusal", False),
    "long-context/tool-trace": (
        "flowtrim-selected",
        "flowtrim-selected",
        "lower-token-safe",
        True,
    ),
    "long-context/handoff": (
        "flowtrim-selected",
        "flowtrim-selected",
        "lower-token-safe",
        True,
    ),
    "long-context/marker-only-unsafe": (
        "raw",
        "insufficient-evidence",
        "insufficient-evidence: guard-failed",
        False,
    ),
    "code-generation/over-abstract-helper": (
        "ponytail-lens",
        "ponytail-lens",
        "code-lens-safe",
        False,
    ),
    "code-generation/duplicate-conversion-logic": (
        "ponytail-lens",
        "ponytail-lens",
        "code-lens-safe",
        False,
    ),
    "mutation/missing-path": (
        "raw",
        "insufficient-evidence",
        "insufficient-evidence: preservation-failed",
        False,
    ),
    "mutation/slower-candidate": (
        "raw",
        "raw",
        "raw-over-wall-time-budget",
        False,
    ),
    "mutation/guard-failure": (
        "raw",
        "insufficient-evidence",
        "insufficient-evidence: guard-failed",
        False,
    ),
}


VAULT_EXPECTATIONS = {
    "vault/short-command": ("raw", "raw", "raw-short-output"),
    "vault/rtk-candidate": ("raw", "raw", "raw-best"),
    "vault/packet-routing": (
        "atlas-context-economy",
        "atlas-context-economy",
        "defer-to-atlas-context-economy",
    ),
    "vault/index-inventory": (
        "atlas-context-economy",
        "atlas-context-economy",
        "defer-to-atlas-context-economy",
    ),
    "vault/source-id-preservation": (
        "atlas-context-economy",
        "atlas-context-economy",
        "defer-to-atlas-context-economy",
    ),
    "vault/approval-boundary": (
        "atlas-context-economy",
        "atlas-context-economy",
        "defer-to-atlas-context-economy",
    ),
}


def write_signal_file(path: Path, index: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    duplicate_line = f"  const repeated{index} = normalizeSharedValue(input);"
    path.write_text(
        "\n".join(
            [
                "export function privateFeature(input: string) {",
                duplicate_line,
                duplicate_line,
                duplicate_line,
                "  return normalizeSharedValue(input);",
                "}",
                "export const wrapper = (value: string) => normalizeSharedValue(value);",
            ]
        ),
        encoding="utf-8",
    )


def create_many_work_repos(work_root: Path, *, repos: int, files: int) -> None:
    for repo_index in range(1, repos + 1):
        repo = work_root / f"private-repo-{repo_index:02d}"
        repo.mkdir()
        subprocess.run(
            ["git", "init"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        for file_index in range(1, files + 1):
            write_signal_file(repo / "src" / f"private_feature_{file_index:02d}.ts", file_index)


class ProofMatrixTest(unittest.TestCase):
    def test_synthetic_profile_proves_each_lane_specific_case(self):
        report = run_suite("synthetic-heavy", FIXTURES_ROOT)
        cases = {case.case_id: case for case in report.cases}

        self.assertEqual(set(cases), set(SYNTHETIC_EXPECTATIONS))
        self.assertEqual(report.vault_verdict, "not-vault")
        self.assertTrue(report.runtime_changes.is_none)

        for case_id, expectation in SYNTHETIC_EXPECTATIONS.items():
            with self.subTest(case_id=case_id):
                selected, winner, reason, counts_as_claim = expectation
                case = cases[case_id]
                self.assertEqual(case.selected_method, selected)
                self.assertEqual(case.winner, winner)
                self.assertEqual(case.decision_reason, reason)
                self.assertEqual(case.counts_as_claim, counts_as_claim)

        self.assertEqual(report.metric_totals["token-bearing"]["wins"], 4)
        self.assertEqual(
            report.metric_totals["refusal-correctness"]["correct_refusals"], 3
        )
        self.assertEqual(report.metric_totals["code-lens"]["wins"], 2)
        self.assertEqual(report.metric_totals["token-bearing"]["insufficient_evidence"], 3)

    def test_required_preservation_items_survive_selected_token_candidates(self):
        report = run_suite("synthetic-heavy", FIXTURES_ROOT)
        required_items = {
            "command-output/noisy-build-pass": (
                "src/example.py",
                "FEATURE_FLAG_DEMO",
                "2 passed",
            ),
            "command-output/noisy-build-fail": (
                "src/worker.py",
                "RetryBudgetExceeded",
                "src/worker.py::test_retry_policy",
            ),
            "long-context/tool-trace": (
                "trace-demo-001",
                "job-demo-17",
                "source:demo-trace-001",
            ),
            "long-context/handoff": (
                "REQ-DEMO-001",
                "tests/test_example.py",
                "src/example.py",
            ),
        }

        for case_id, items in required_items.items():
            with self.subTest(case_id=case_id):
                case = next(case for case in report.cases if case.case_id == case_id)
                selected = next(
                    method for method in case.methods if method.method == case.selected_method
                )
                snippet = (selected.payload or {}).get("sanitized_snippet", "")
                for item in items:
                    self.assertIn(item, snippet)

    def test_headroom_skipped_is_neutral_and_claim_limited(self):
        report = run_suite("synthetic-heavy", FIXTURES_ROOT)
        headroom_methods = [
            method
            for case in report.cases
            for method in case.methods
            if method.method == "headroom-direct"
        ]

        self.assertTrue(headroom_methods)
        self.assertTrue(all(method.status == "skipped" for method in headroom_methods))
        self.assertFalse(any(case.winner == "headroom-direct" for case in report.cases))
        self.assertTrue(
            validate_claim(report, "Headroom was skipped because it was unavailable.")
        )
        self.assertFalse(validate_claim(report, "Headroom lost to FlowTrim."))

    def test_vault_profile_keeps_atlas_context_economy_as_default(self):
        report = run_suite(
            "aql-vault-readonly",
            FIXTURES_ROOT,
            aql_root=ROOT,
        )
        cases = {case.case_id: case for case in report.cases}

        self.assertEqual(set(cases), set(VAULT_EXPECTATIONS))
        self.assertEqual(report.vault_verdict, "hybrid-only")
        self.assertEqual(report.metric_totals["token-bearing"]["wins"], 0)
        self.assertEqual(report.metric_totals["vault-semantic"]["atlas_deferrals"], 4)
        self.assertTrue(report.runtime_changes.is_none)

        for case_id, expectation in VAULT_EXPECTATIONS.items():
            with self.subTest(case_id=case_id):
                selected, winner, reason = expectation
                case = cases[case_id]
                self.assertEqual(case.selected_method, selected)
                self.assertEqual(case.winner, winner)
                self.assertEqual(case.decision_reason, reason)

        text = report_to_json(report)
        self.assertNotIn(str(ROOT), text)
        self.assertEqual(scan_text(text), ())

    def test_work_profile_defaults_to_anonymous_nine_by_twelve_code_lens_sample(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            work_root = Path(tmpdir)
            create_many_work_repos(work_root, repos=10, files=13)
            report = run_suite(
                "work-code-readonly",
                FIXTURES_ROOT,
                work_root=work_root,
            )
            direct_cases = build_work_code_readonly_suite(work_root)
            text = report_to_json(report)
            data = json.loads(text)

        self.assertEqual(len(report.cases), 108)
        self.assertEqual(len(direct_cases), 108)
        self.assertEqual(data["metric_totals"]["code-lens"]["cases"], 108)
        self.assertEqual(data["metric_totals"]["code-lens"]["wins"], 108)
        self.assertEqual(data["metric_totals"]["token-bearing"]["cases"], 0)
        self.assertEqual(data["metric_totals"]["token-bearing"]["wins"], 0)
        self.assertTrue(report.runtime_changes.is_none)
        self.assertIn("work-code/repo-09/file-12", {case.case_id for case in report.cases})
        self.assertNotIn(str(work_root), text)
        self.assertNotIn("private-repo", text)
        self.assertNotIn("private_feature", text)
        self.assertNotIn("normalizeSharedValue", text)
        self.assertEqual(scan_text(text), ())

    def test_publication_claims_match_proof_boundaries(self):
        synthetic = run_suite("synthetic-heavy", FIXTURES_ROOT)
        vault = run_suite("aql-vault-readonly", FIXTURES_ROOT)

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
        self.assertTrue(
            validate_claim(
                synthetic,
                "Ponytail lens reduced code complexity without claiming direct token compression.",
            )
        )
        self.assertTrue(
            validate_claim(
                vault,
                "Vault verdict is hybrid-only; Atlas context economy remains default.",
            )
        )
        self.assertFalse(
            validate_claim(
                synthetic,
                "FlowTrim beats RTK, Ponytail, and Headroom globally.",
            )
        )
        self.assertFalse(validate_claim(synthetic, "Ponytail saved tokens."))
        self.assertFalse(validate_claim(vault, "FlowTrim is vault-safe."))

    def test_tracked_files_and_benchmark_reports_are_privacy_safe(self):
        tracked = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        findings = {}
        for relative in tracked:
            path = ROOT / relative
            if not path.is_file():
                continue
            if "benchmarks/reports/" in relative:
                continue
            hits = scan_text(path.read_text(errors="ignore"))
            if hits:
                findings[relative] = hits

        reports = [
            report_to_json(run_suite("synthetic-heavy", FIXTURES_ROOT)),
            report_to_json(run_suite("aql-vault-readonly", FIXTURES_ROOT, aql_root=ROOT)),
        ]
        for index, text in enumerate(reports, start=1):
            hits = scan_text(text)
            if hits:
                findings[f"generated-report-{index}"] = hits

        self.assertEqual(findings, {})


if __name__ == "__main__":
    unittest.main()
