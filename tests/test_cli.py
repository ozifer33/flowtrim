import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_suite import create_work_repo
from tests.test_work_commit_history import create_history_repo
from tests.test_public_corpus import create_public_history_repo, write_manifest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "flowtrim" / "scripts" / "flowtrim_benchmark.py"
ORCHESTRATOR_SCRIPT = ROOT / "skills" / "flowtrim" / "scripts" / "flowtrim_orchestrator.py"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "src"},
    )


def run_module(module: str, *args):
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "src"},
    )


def run_orchestrator_script(*args):
    return subprocess.run(
        [sys.executable, str(ORCHESTRATOR_SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "src"},
    )


class CliTest(unittest.TestCase):
    def test_legacy_text_mode_prints_token_estimate(self):
        result = run_cli("abcd")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "1")

    def test_package_benchmark_module_prints_token_estimate(self):
        result = run_module("flowtrim.cli.benchmark", "abcd")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "1")

    def test_package_orchestrator_module_classifies_command_output(self):
        result = run_module(
            "flowtrim.cli.orchestrator",
            "npm test produced a long build log",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "command-output")

    def test_orchestrator_script_wrapper_still_classifies_command_output(self):
        result = run_orchestrator_script("npm test produced a long build log")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "command-output")

    def test_suite_json_mode_prints_benchmark_report(self):
        result = run_cli("suite", "--profile", "synthetic-heavy", "--format", "json")

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["schema"], "flowtrim-benchmark/v1")
        self.assertEqual(data["profile"], "synthetic-heavy")
        self.assertNotIn("/".join(("", "Users", "")), result.stdout)

    def test_suite_cli_with_aql_root_does_not_expose_root_path(self):
        result = run_cli(
            "suite",
            "--profile",
            "aql-vault-readonly",
            "--format",
            "json",
            "--aql-root",
            str(ROOT),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(str(ROOT), result.stdout)

    def test_suite_cli_with_work_root_does_not_expose_root_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            work_root = Path(tmpdir)
            create_work_repo(work_root)

            result = run_cli(
                "suite",
                "--profile",
                "work-code-readonly",
                "--format",
                "json",
                "--work-root",
                str(work_root),
                "--repo-limit",
                "1",
                "--files-per-repo",
                "1",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["profile"], "work-code-readonly")
        self.assertNotIn(str(work_root), result.stdout)
        self.assertNotIn("veryUniquePrivateLogicName", result.stdout)
        self.assertNotIn("repo-a", result.stdout)
        self.assertNotIn("feature.ts", result.stdout)
        self.assertNotIn("normalizeSharedValue", result.stdout)

    def test_suite_cli_with_work_repo_history_does_not_expose_repo_details(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            work_root = Path(tmpdir)
            repo = create_history_repo(work_root, "private-ruejai-app", "dart")

            result = run_cli(
                "suite",
                "--profile",
                "work-commit-history-readonly",
                "--format",
                "json",
                "--work-repo",
                str(repo),
                "--commit-limit",
                "4",
                "--files-per-commit",
                "1",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["profile"], "work-commit-history-readonly")
        self.assertIn("work-history/repo-01/commit-001/code-01", result.stdout)
        self.assertNotIn(str(work_root), result.stdout)
        self.assertNotIn("private-ruejai-app", result.stdout)
        self.assertNotIn("private_feature", result.stdout)
        self.assertNotIn("normalizePrivateFixtureValue", result.stdout)

    def test_suite_cli_work_markdown_omits_repo_file_names_and_source_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            work_root = Path(tmpdir)
            create_work_repo(work_root)

            result = run_cli(
                "suite",
                "--profile",
                "work-code-readonly",
                "--format",
                "markdown",
                "--work-root",
                str(work_root),
                "--repo-limit",
                "1",
                "--files-per-repo",
                "1",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("high-signal files", result.stdout)
        self.assertNotIn(str(work_root), result.stdout)
        self.assertNotIn("repo-a", result.stdout)
        self.assertNotIn("feature.ts", result.stdout)
        self.assertNotIn("normalizeSharedValue", result.stdout)

    def test_suite_cli_work_write_report_rejects_target_under_work_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            work_root = Path(tmpdir)
            create_work_repo(work_root)
            reports_dir = work_root / "reports"

            result = run_cli(
                "suite",
                "--profile",
                "work-code-readonly",
                "--format",
                "json",
                "--work-root",
                str(work_root),
                "--reports-dir",
                str(reports_dir),
                "--write-report",
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reports-dir must not be inside work-root", result.stderr)
        self.assertFalse(reports_dir.exists())

    def test_write_report_rejects_target_at_work_root_for_any_profile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            work_root = Path(tmpdir)
            result = run_cli(
                "suite",
                "--profile",
                "synthetic-heavy",
                "--format",
                "json",
                "--work-root",
                str(work_root),
                "--reports-dir",
                str(work_root),
                "--write-report",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("reports-dir must not be inside work-root", result.stderr)
            self.assertFalse((work_root / "synthetic-heavy.json").exists())

    def test_write_report_rejects_target_at_repo_root(self):
        result = run_cli(
            "suite",
            "--profile",
            "synthetic-heavy",
            "--format",
            "json",
            "--reports-dir",
            str(ROOT),
            "--write-report",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reports-dir must not be inside repo-root", result.stderr)
        self.assertFalse((ROOT / "synthetic-heavy.json").exists())

    def test_public_corpus_prepare_cli_prints_sanitized_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_repo, pinned = create_public_history_repo(root)
            manifest = write_manifest(root / "manifest.json", pinned_commit=pinned)
            manifest_data = json.loads(manifest.read_text())
            manifest_data["repos"][0]["url"] = "https://github.com/example/public-source.git"
            manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
            cache_root = root / "cache"

            result = run_cli(
                "public-corpus",
                "prepare",
                "--manifest",
                str(manifest),
                "--cache-root",
                str(cache_root),
                "--source-override",
                "repo-01",
                str(source_repo),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["prepared"], 1)
        self.assertEqual(data["repos"][0]["alias"], "repo-01")
        self.assertNotIn(str(root), result.stdout)
        self.assertNotIn("public-source", result.stdout)

    def test_public_corpus_prepare_rejects_cache_under_repo_root(self):
        result = run_cli(
            "public-corpus",
            "prepare",
            "--manifest",
            str(ROOT / "missing-manifest.json"),
            "--cache-root",
            str(ROOT / "public-cache"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cache-root must not be inside repo-root", result.stderr)
        self.assertFalse((ROOT / "public-cache").exists())

    def test_public_corpus_suite_cli_uses_prepared_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_repo, pinned = create_public_history_repo(root)
            manifest = write_manifest(root / "manifest.json", pinned_commit=pinned)
            cache_root = root / "cache"
            cache_root.mkdir()
            subprocess.run(
                ["git", "clone", str(source_repo), str(cache_root / "repo-01")],
                check=True,
                capture_output=True,
                text=True,
            )

            result = run_cli(
                "suite",
                "--profile",
                "public-open-source-readonly",
                "--format",
                "json",
                "--public-corpus-manifest",
                str(manifest),
                "--public-cache-root",
                str(cache_root),
                "--commit-limit",
                "4",
                "--files-per-commit",
                "1",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["profile"], "public-open-source-readonly")
        self.assertTrue(any("/control-" in case["case_id"] for case in data["cases"]))
        self.assertNotIn(str(root), result.stdout)
        self.assertNotIn("public-source", result.stdout)

    def test_compare_cli_prints_aggregate_markdown_without_report_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            baseline_result = run_cli("suite", "--profile", "synthetic-heavy", "--format", "json")
            candidate.write_text(baseline_result.stdout, encoding="utf-8")
            baseline.write_text(baseline_result.stdout, encoding="utf-8")

            result = run_cli(
                "compare",
                "--baseline-report",
                str(baseline),
                "--candidate-report",
                str(candidate),
                "--focus",
                "headroom-direct",
                "--format",
                "markdown",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# FlowTrim Comparison", result.stdout)
        self.assertIn("headroom-direct", result.stdout)
        self.assertNotIn(str(root), result.stdout)
        self.assertNotIn("baseline.json", result.stdout)
        self.assertNotIn("candidate.json", result.stdout)

    def test_claim_check_cli_accepts_allowed_claim_and_rejects_overclaim(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report_path = root / "report.json"
            report_result = run_cli("suite", "--profile", "synthetic-heavy", "--format", "json")
            report_path.write_text(report_result.stdout, encoding="utf-8")

            allowed = run_cli(
                "claim-check",
                "--report",
                str(report_path),
                "--claim",
                "FlowTrim selected a safe lower-token method for this measured lane.",
                "--format",
                "json",
            )
            forbidden = run_cli(
                "claim-check",
                "--report",
                str(report_path),
                "--claim",
                "FlowTrim beats RTK, Ponytail, and Headroom globally.",
                "--format",
                "json",
            )

        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        allowed_data = json.loads(allowed.stdout)
        self.assertEqual(allowed_data["schema"], "flowtrim-claim-check/v1")
        self.assertTrue(allowed_data["valid"])
        self.assertNotIn(str(root), allowed.stdout)

        self.assertNotEqual(forbidden.returncode, 0)
        forbidden_data = json.loads(forbidden.stdout)
        self.assertFalse(forbidden_data["valid"])
        self.assertEqual(forbidden_data["claim_scope"], "rejected")
        self.assertNotIn(str(root), forbidden.stdout)

    def test_privacy_scan_cli_is_aggregate_and_blocks_findings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            safe = root / "safe.txt"
            unsafe = root / "unsafe.txt"
            safe.write_text("public corpus summary only", encoding="utf-8")
            unsafe.write_text("/" + "Users" + "/private/project", encoding="utf-8")

            safe_result = run_cli(
                "privacy-scan",
                "--path",
                str(safe),
                "--format",
                "json",
            )
            unsafe_result = run_cli(
                "privacy-scan",
                "--path",
                str(unsafe),
                "--format",
                "json",
            )

        self.assertEqual(safe_result.returncode, 0, safe_result.stderr)
        safe_data = json.loads(safe_result.stdout)
        self.assertEqual(safe_data["schema"], "flowtrim-privacy-scan/v1")
        self.assertEqual(safe_data["findings"], [])
        self.assertEqual(safe_data["files_scanned"], 1)
        self.assertNotIn(str(root), safe_result.stdout)

        self.assertNotEqual(unsafe_result.returncode, 0)
        unsafe_data = json.loads(unsafe_result.stdout)
        self.assertEqual(unsafe_data["files_scanned"], 1)
        self.assertEqual(unsafe_data["findings"][0]["target"], "input-001")
        self.assertIn("private-path", unsafe_data["findings"][0]["finding"])
        self.assertNotIn(str(root), unsafe_result.stdout)

    def test_release_check_cli_reports_readiness_without_report_path_leak(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report_path = root / "report.json"
            report_result = run_cli("suite", "--profile", "synthetic-heavy", "--format", "json")
            report_path.write_text(report_result.stdout, encoding="utf-8")

            ready = run_cli(
                "release-check",
                "--report",
                str(report_path),
                "--unit-tests-passed",
                "--skill-validation-passed",
                "--benchmark-smoke-passed",
                "--privacy-scan-passed",
                "--sanitized-report-present",
                "--package-entrypoint-ready",
                "--license-reviewed",
                "--tool-versions-captured",
                "--format",
                "json",
            )
            blocked = run_cli(
                "release-check",
                "--report",
                str(report_path),
                "--unit-tests-passed",
                "--skill-validation-passed",
                "--benchmark-smoke-passed",
                "--privacy-scan-passed",
                "--sanitized-report-present",
                "--package-entrypoint-ready",
                "--license-reviewed",
                "--format",
                "json",
            )

        self.assertEqual(ready.returncode, 0, ready.stderr)
        ready_data = json.loads(ready.stdout)
        self.assertEqual(ready_data["schema"], "flowtrim-release-check/v1")
        self.assertTrue(ready_data["ready"])
        self.assertIn("allowed_claims", ready_data)
        self.assertNotIn(str(root), ready.stdout)

        self.assertNotEqual(blocked.returncode, 0)
        blocked_data = json.loads(blocked.stdout)
        self.assertFalse(blocked_data["ready"])
        self.assertIn("tool availability or version evidence is missing", blocked_data["blockers"])
        self.assertNotIn(str(root), blocked.stdout)

    def test_skill_check_cli_accepts_flowtrim_skill(self):
        result = run_cli(
            "skill-check",
            "--skill-root",
            "skills/flowtrim",
            "--format",
            "json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["schema"], "flowtrim-skill-check/v1")
        self.assertTrue(data["valid"])
        self.assertEqual(data["findings"], [])

    def test_skill_check_cli_rejects_malformed_skill_without_path_leak(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            skill_root = root / "bad-skill"
            skill_root.mkdir()
            (skill_root / "SKILL.md").write_text(
                "---\nname: bad\n---\n# Bad Skill\n\n## Commands\n",
                encoding="utf-8",
            )

            result = run_cli(
                "skill-check",
                "--skill-root",
                str(skill_root),
                "--format",
                "json",
            )

        self.assertNotEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["schema"], "flowtrim-skill-check/v1")
        self.assertFalse(data["valid"])
        self.assertTrue(data["findings"])
        self.assertEqual(data["findings"][0]["target"], "skill-root")
        self.assertNotIn(str(root), result.stdout)

    def test_suite_markdown_mode_omits_raw_private_output(self):
        result = run_cli("suite", "--profile", "aql-vault-readonly", "--format", "markdown")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# FlowTrim Benchmark Report", result.stdout)
        self.assertIn("aql-vault-readonly", result.stdout)
        self.assertNotIn("/".join(("", "Users", "")), result.stdout)

    def test_write_report_writes_to_requested_reports_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_cli(
                "suite",
                "--profile",
                "synthetic-heavy",
                "--format",
                "json",
                "--reports-dir",
                tmpdir,
                "--write-report",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(str(Path(tmpdir)), result.stdout)
            path = Path(tmpdir) / "synthetic-heavy.json"
            self.assertEqual(path.parent, Path(tmpdir))
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text())["profile"], "synthetic-heavy")

    def test_suite_does_not_write_default_report_without_flag(self):
        reports_dir = ROOT / "benchmarks" / "reports"
        if reports_dir.exists():
            shutil.rmtree(reports_dir)

        result = run_cli("suite", "--profile", "synthetic-heavy", "--format", "json")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(reports_dir.exists())

    def test_write_report_default_path_is_ignored_relative_path(self):
        reports_dir = ROOT / "benchmarks" / "reports"
        if reports_dir.exists():
            shutil.rmtree(reports_dir)

        try:
            result = run_cli(
                "suite",
                "--profile",
                "synthetic-heavy",
                "--format",
                "json",
                "--write-report",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "report written: synthetic-heavy.json")
            self.assertTrue((reports_dir / "synthetic-heavy.json").exists())
        finally:
            if reports_dir.exists():
                shutil.rmtree(reports_dir)


if __name__ == "__main__":
    unittest.main()
