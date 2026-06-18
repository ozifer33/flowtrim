import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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
