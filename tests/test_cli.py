import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_suite import create_work_repo
from tests.test_work_commit_history import create_history_repo


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "flowtrim" / "scripts" / "flowtrim_benchmark.py"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
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
