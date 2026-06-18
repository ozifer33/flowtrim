import unittest

from flowtrim.models import Lane
from flowtrim.native_command import FlowTrimNativeCommand, compact_command_output


class NativeCommandTest(unittest.TestCase):
    def test_compacts_noisy_passing_build_and_preserves_required_facts(self):
        text = "\n".join(
            [
                "BUILD START demo-web",
                "src/example.py::test_user_flow PASSED",
                "src/example.py::test_billing_summary PASSED",
                "WARN keep: src/example.py uses FEATURE_FLAG_DEMO",
                "INFO noise: bundler chunk 001 completed",
                "INFO noise: bundler chunk 002 completed",
                "SUMMARY keep: 2 passed, 0 failed, artifact demo-build",
            ]
        )

        measurement = FlowTrimNativeCommand().measure(
            text,
            Lane.COMMAND_OUTPUT,
            must_preserve=("src/example.py", "FEATURE_FLAG_DEMO", "2 passed"),
        )

        self.assertEqual(measurement.method, "flowtrim-native-command")
        self.assertTrue(measurement.guard_passed)
        self.assertLess(measurement.tokens, 18)
        self.assertEqual(measurement.payload["status"], "pass")
        self.assertIn("src/example.py", measurement.payload["primary_files"])
        self.assertIn("FEATURE_FLAG_DEMO", measurement.payload["must_keep"])
        self.assertIn("2 passed", measurement.payload["sanitized_snippet"])
        self.assertNotIn("raw_output", measurement.payload)

    def test_compacts_failing_build_and_preserves_error_and_failing_test(self):
        text = "\n".join(
            [
                "BUILD START demo-worker",
                "src/worker.py::test_retry_policy FAILED",
                "ERROR keep: RetryBudgetExceeded",
                "TRACE keep: src/worker.py:42 handle_retry",
                "INFO noise: dependency cache warmed 001",
                "SUMMARY keep: 1 failed, 18 passed, failing test src/worker.py::test_retry_policy",
            ]
        )

        packet = compact_command_output(
            text,
            must_preserve=(
                "src/worker.py",
                "RetryBudgetExceeded",
                "src/worker.py::test_retry_policy",
            ),
        )

        self.assertTrue(packet.guard_passed)
        self.assertEqual(packet.payload["status"], "fail")
        self.assertIn("src/worker.py", packet.payload["primary_files"])
        self.assertIn("src/worker.py::test_retry_policy", packet.payload["failing_tests"])
        self.assertIn("RetryBudgetExceeded", packet.payload["error_labels"])

    def test_missing_required_fact_fails_guard(self):
        packet = compact_command_output(
            "ERROR keep: RetryBudgetExceeded",
            must_preserve=("src/worker.py", "RetryBudgetExceeded"),
        )

        self.assertFalse(packet.guard_passed)
        self.assertIn("missing required items", packet.reason)


if __name__ == "__main__":
    unittest.main()
