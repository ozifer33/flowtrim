import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_SCRIPT = ROOT / "skills" / "flowtrim" / "scripts" / "flowtrim_run.py"

PASS_SCRIPT = (
    "import sys\n"
    "print('BUILD START demo-api')\n"
    "for index in range(40):\n"
    "    print(f'INFO noise: bundler chunk {index:03d} completed')\n"
    "print('src/api.py::test_create PASSED')\n"
    "print('SUMMARY keep: 12 passed, 0 failed')\n"
)
FAIL_SCRIPT = (
    "import sys\n"
    "print('BUILD START demo-api')\n"
    "for index in range(40):\n"
    "    print(f'INFO noise: bundler chunk {index:03d} completed')\n"
    "print('src/api.py::test_create FAILED')\n"
    "print('ERROR: TimeoutBudgetError while creating order')\n"
    "print('SUMMARY keep: 1 failed, 11 passed')\n"
    "sys.exit(3)\n"
)


def run_wrapper(*args):
    return subprocess.run(
        [sys.executable, str(RUN_SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "src"},
    )


class RunCliTest(unittest.TestCase):
    def test_passing_command_is_trimmed_and_exit_code_stays_zero(self):
        result = run_wrapper("--", sys.executable, "-c", PASS_SCRIPT)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status: pass", result.stdout)
        self.assertIn("12 passed", result.stdout)
        self.assertNotIn("INFO noise", result.stdout)
        self.assertIn("exit 0", result.stderr)
        self.assertIn("trimmed", result.stderr)

    def test_failing_command_keeps_error_excerpt_and_propagates_exit_code(self):
        result = run_wrapper("--", sys.executable, "-c", FAIL_SCRIPT)

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("TimeoutBudgetError", result.stdout)
        self.assertIn("src/api.py::test_create FAILED", result.stdout)
        self.assertIn("[flowtrim: omitted", result.stdout)
        self.assertIn("exit 3", result.stderr)

    def test_trim_on_fail_produces_fact_packet_with_fail_status(self):
        result = run_wrapper("--trim-on-fail", "--", sys.executable, "-c", FAIL_SCRIPT)

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("status: fail", result.stdout)
        self.assertIn("src/api.py::test_create", result.stdout)
        self.assertNotIn("INFO noise", result.stdout)

    def test_raw_on_fail_prints_full_output(self):
        result = run_wrapper("--raw-on-fail", "--", sys.executable, "-c", FAIL_SCRIPT)

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("INFO noise: bundler chunk 000 completed", result.stdout)
        self.assertIn("TimeoutBudgetError", result.stdout)

    def test_json_mode_reports_exit_code_and_action(self):
        result = run_wrapper("--format", "json", "--", sys.executable, "-c", FAIL_SCRIPT)

        self.assertEqual(result.returncode, 3, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["schema"], "flowtrim-run/v1")
        self.assertEqual(data["exit_code"], 3)
        self.assertEqual(data["action"], "excerpt")
        self.assertLess(data["output_tokens"], data["baseline_tokens"])

    def test_missing_command_is_a_usage_error(self):
        result = run_wrapper("--format", "json")

        self.assertEqual(result.returncode, 2)
        self.assertIn("a command is required", result.stderr)

    def test_unknown_executable_fails_without_path_leak(self):
        result = run_wrapper("--", "definitely-not-a-real-binary-9f8a7b")

        self.assertEqual(result.returncode, 2)
        self.assertIn("could not be started", result.stderr)


if __name__ == "__main__":
    unittest.main()
