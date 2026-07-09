import json
import subprocess
import sys
import unittest
from pathlib import Path

from flowtrim.metrics import estimate_tokens
from flowtrim.models import Lane
from flowtrim.trim import trim_text

from tests.test_cli import run_module


ROOT = Path(__file__).resolve().parents[1]
TRIM_SCRIPT = ROOT / "skills" / "flowtrim" / "scripts" / "flowtrim_trim.py"
NOISY_FAIL_LOG = ROOT / "benchmarks" / "fixtures" / "logs" / "noisy-build-fail.txt"
NOISY_FAIL_MUST_PRESERVE = (
    "src/worker.py",
    "RetryBudgetExceeded",
    "src/worker.py::test_retry_policy",
)


def run_trim_script(*args, stdin_text=None):
    return subprocess.run(
        [sys.executable, str(TRIM_SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        input=stdin_text,
        env={"PYTHONPATH": "src"},
    )


class TrimTextTest(unittest.TestCase):
    def test_trims_noisy_fail_fixture_and_preserves_required_facts(self):
        text = NOISY_FAIL_LOG.read_text(encoding="utf-8")

        decision = trim_text(text, must_preserve=NOISY_FAIL_MUST_PRESERVE)

        self.assertEqual(decision.action, "trimmed")
        self.assertEqual(decision.lane, Lane.COMMAND_OUTPUT)
        self.assertLess(decision.output_tokens, decision.baseline_tokens)
        self.assertGreaterEqual(decision.savings, 0.5)
        for item in NOISY_FAIL_MUST_PRESERVE:
            self.assertIn(item, decision.text)
        self.assertIn("status: fail", decision.text)
        self.assertEqual(decision.output_tokens, estimate_tokens(decision.text))

    def test_trimmed_packet_keeps_every_failing_test_id(self):
        text = "\n".join(
            [
                "BUILD START demo-api",
                "src/api.py::test_create FAILED",
                "src/api.py::test_update FAILED",
                "src/api.py::test_delete FAILED",
                "INFO noise: dependency cache warmed 001",
                "INFO noise: dependency cache warmed 002",
                "INFO noise: dependency cache warmed 003",
                "INFO noise: dependency cache warmed 004",
                "SUMMARY keep: 3 failed, 9 passed",
            ]
        )

        decision = trim_text(text)

        self.assertEqual(decision.action, "trimmed")
        for test_id in (
            "src/api.py::test_create",
            "src/api.py::test_update",
            "src/api.py::test_delete",
        ):
            self.assertIn(test_id, decision.text)

    def test_exact_evidence_lane_returns_raw_unchanged(self):
        text = NOISY_FAIL_LOG.read_text(encoding="utf-8")

        decision = trim_text(text, lane=Lane.EXACT_EVIDENCE)

        self.assertEqual(decision.action, "raw")
        self.assertEqual(decision.text, text)
        self.assertEqual(decision.output_tokens, decision.baseline_tokens)
        self.assertIn("exact-evidence", decision.reason)

    def test_exact_task_classification_routes_to_raw(self):
        text = NOISY_FAIL_LOG.read_text(encoding="utf-8")

        decision = trim_text(text, task="review the exact stack trace for this failure")

        self.assertEqual(decision.action, "raw")
        self.assertEqual(decision.text, text)

    def test_missing_required_fact_falls_back_to_raw(self):
        text = NOISY_FAIL_LOG.read_text(encoding="utf-8")

        decision = trim_text(text, must_preserve=("fact-not-in-the-log",))

        self.assertEqual(decision.action, "raw")
        self.assertEqual(decision.text, text)
        self.assertIn("missing required items", decision.reason)

    def test_input_smaller_than_packet_falls_back_to_raw(self):
        decision = trim_text("2 passed")

        self.assertEqual(decision.action, "raw")
        self.assertEqual(decision.text, "2 passed")
        self.assertIn("no token savings", decision.reason)

    def test_trim_is_deterministic(self):
        text = NOISY_FAIL_LOG.read_text(encoding="utf-8")

        first = trim_text(text, must_preserve=NOISY_FAIL_MUST_PRESERVE)
        second = trim_text(text, must_preserve=NOISY_FAIL_MUST_PRESERVE)

        self.assertEqual(first, second)


TOOL_TRACE = ROOT / "benchmarks" / "fixtures" / "context" / "tool-trace.json"
HANDOFF = ROOT / "benchmarks" / "fixtures" / "context" / "handoff.md"


class LongContextTrimTest(unittest.TestCase):
    def test_tool_trace_keeps_ids_files_and_error(self):
        text = TOOL_TRACE.read_text(encoding="utf-8")

        decision = trim_text(
            text,
            lane=Lane.LONG_CONTEXT,
            must_preserve=("trace-demo-001", "job-demo-17", "source:demo-trace-001"),
        )

        self.assertEqual(decision.action, "trimmed")
        for fact in (
            "trace-demo-001",
            "job-demo-17",
            "source:demo-trace-001",
            "src/example.py",
            "DEMO_FAILURE",
        ):
            self.assertIn(fact, decision.text)
        self.assertGreaterEqual(decision.savings, 0.4)

    def test_handoff_keeps_requirement_and_paths(self):
        text = HANDOFF.read_text(encoding="utf-8")

        decision = trim_text(
            text,
            lane=Lane.LONG_CONTEXT,
            must_preserve=("REQ-DEMO-001", "tests/test_example.py", "src/example.py"),
        )

        self.assertEqual(decision.action, "trimmed")
        for fact in ("REQ-DEMO-001", "tests/test_example.py", "src/example.py"):
            self.assertIn(fact, decision.text)

    def test_long_context_task_classification_selects_reducer(self):
        text = TOOL_TRACE.read_text(encoding="utf-8")

        decision = trim_text(text, task="compact this json tool trace payload")

        self.assertEqual(decision.lane, Lane.LONG_CONTEXT)
        self.assertEqual(decision.action, "trimmed")

    def test_long_context_missing_fact_falls_back_to_raw(self):
        text = HANDOFF.read_text(encoding="utf-8")

        decision = trim_text(
            text,
            lane=Lane.LONG_CONTEXT,
            must_preserve=("fact-not-in-handoff",),
        )

        self.assertEqual(decision.action, "raw")
        self.assertEqual(decision.text, text)


class ExcerptFallbackTest(unittest.TestCase):
    def build_log(self):
        middle = "vendor replied with code ZX-99Q so retry was skipped"
        return "\n".join(
            [
                "JOB START nightly-sync",
                *[f"progress tick {index:03d} ok" for index in range(60)],
                middle,
                *[f"progress tick {index:03d} ok" for index in range(60, 120)],
                "JOB END nightly-sync",
            ]
        ), middle

    def test_unreadable_format_with_excerpt_fallback_keeps_head_and_tail(self):
        text, _ = self.build_log()

        decision = trim_text(text, fallback="excerpt")

        self.assertEqual(decision.action, "excerpt")
        self.assertIn("JOB START nightly-sync", decision.text)
        self.assertIn("JOB END nightly-sync", decision.text)
        self.assertIn("[flowtrim: omitted", decision.text)
        self.assertLess(decision.output_tokens, decision.baseline_tokens)
        self.assertIn("packet rejected", decision.reason)

    def test_unreadable_format_without_fallback_stays_raw(self):
        text, _ = self.build_log()

        decision = trim_text(text)

        self.assertEqual(decision.action, "raw")
        self.assertEqual(decision.text, text)
        self.assertIn("no extractable facts", decision.reason)

    def test_must_preserve_fact_rides_in_packet_when_extraction_is_empty(self):
        text, middle = self.build_log()

        decision = trim_text(text, must_preserve=(middle,), fallback="excerpt")

        self.assertEqual(decision.action, "trimmed")
        self.assertIn(middle, decision.text)

    def test_excerpt_still_raw_when_fact_is_absent(self):
        text, _ = self.build_log()

        decision = trim_text(
            text,
            must_preserve=("fact-that-does-not-exist",),
            fallback="excerpt",
        )

        self.assertEqual(decision.action, "raw")
        self.assertEqual(decision.text, text)

    def test_cli_fallback_excerpt_flag(self):
        text, _ = self.build_log()

        result = run_trim_script(
            "--fallback",
            "excerpt",
            "--format",
            "json",
            stdin_text=text,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["action"], "excerpt")
        self.assertIn("[flowtrim: omitted", data["text"])


class TrimCliTest(unittest.TestCase):
    def test_cli_trims_fixture_file_and_prints_stats_to_stderr(self):
        result = run_module(
            "flowtrim.cli.trim",
            "--file",
            str(NOISY_FAIL_LOG),
            *[arg for item in NOISY_FAIL_MUST_PRESERVE for arg in ("--must-preserve", item)],
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        raw_tokens = estimate_tokens(NOISY_FAIL_LOG.read_text(encoding="utf-8"))
        self.assertLess(estimate_tokens(result.stdout), raw_tokens)
        for item in NOISY_FAIL_MUST_PRESERVE:
            self.assertIn(item, result.stdout)
        self.assertIn("% saved", result.stderr)

    def test_cli_reads_stdin_and_emits_json_decision(self):
        text = NOISY_FAIL_LOG.read_text(encoding="utf-8")

        result = run_trim_script("--format", "json", stdin_text=text)

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["schema"], "flowtrim-trim/v1")
        self.assertEqual(data["action"], "trimmed")
        self.assertEqual(data["lane"], "command-output")
        self.assertGreater(data["savings_ratio"], 0)
        self.assertLess(data["output_tokens"], data["baseline_tokens"])

    def test_cli_exact_lane_passes_input_through_verbatim(self):
        text = NOISY_FAIL_LOG.read_text(encoding="utf-8")

        result = run_trim_script("--lane", "exact-evidence", stdin_text=text)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(result.stdout, text)
        self.assertIn("raw fallback", result.stderr)

    def test_cli_quiet_suppresses_stats_line(self):
        result = run_trim_script(
            "--file",
            str(NOISY_FAIL_LOG),
            "--quiet",
            stdin_text="",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")

    def test_cli_unreadable_file_fails_without_path_leak(self):
        missing = str(ROOT / "does-not-exist" / "missing.log")

        result = run_trim_script("--file", missing, stdin_text="")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("input file is unreadable", result.stderr)
        self.assertNotIn(missing, result.stderr)


if __name__ == "__main__":
    unittest.main()
