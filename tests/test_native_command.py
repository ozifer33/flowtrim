import unittest
from pathlib import Path

from flowtrim.metrics import estimate_tokens
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
        self.assertLess(measurement.tokens, estimate_tokens(text) // 2)
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

    def test_absent_must_preserve_item_is_not_fabricated_into_packet(self):
        packet = compact_command_output(
            "ERROR keep: RetryBudgetExceeded",
            must_preserve=("src/worker.py", "RetryBudgetExceeded"),
        )

        self.assertNotIn("src/worker.py", packet.text)

    def test_urls_and_dates_are_not_reported_as_files(self):
        packet = compact_command_output(
            "\n".join(
                [
                    "fetching https://registry.example.com/react/-/react-18.2.0.tgz",
                    "run started 2026/07/08 at 10:00",
                    "compiling src/app/main.py",
                ]
            )
        )

        self.assertEqual(packet.payload["primary_files"], ["src/app/main.py"])


REAL_LOG_ROOT = Path(__file__).resolve().parent / "fixtures" / "logs"


class RealWorldLogsTest(unittest.TestCase):
    def read_log(self, name):
        return (REAL_LOG_ROOT / name).read_text(encoding="utf-8")

    def assert_compacts(self, text, *, minimum_ratio=0.5):
        packet = compact_command_output(text)
        raw_tokens = estimate_tokens(text)
        packet_tokens = estimate_tokens(packet.text)
        self.assertLess(packet_tokens, raw_tokens)
        self.assertGreaterEqual((raw_tokens - packet_tokens) / raw_tokens, minimum_ratio)
        return packet

    def test_pytest_log_keeps_failing_test_id_and_error(self):
        packet = self.assert_compacts(self.read_log("pytest-real-fail.txt"))

        self.assertEqual(packet.payload["status"], "fail")
        self.assertIn(
            "tests/test_billing.py::test_prorates_mid_cycle_change",
            packet.payload["failing_tests"],
        )
        self.assertIn("AssertionError", packet.payload["error_labels"])
        self.assertIn("tests/test_billing.py::test_prorates_mid_cycle_change", packet.text)

    def test_jest_log_keeps_failing_suite_and_test_name(self):
        packet = self.assert_compacts(self.read_log("jest-fail.txt"))

        self.assertEqual(packet.payload["status"], "fail")
        self.assertIn("src/services/payment.test.ts", packet.payload["failing_tests"])
        self.assertIn(
            "PaymentService › charges the saved card",
            packet.payload["failing_tests"],
        )
        self.assertTrue(
            any("1 failed" in line for line in packet.payload["summary_lines"])
        )

    def test_go_log_keeps_failing_test_name(self):
        packet = self.assert_compacts(self.read_log("go-fail.txt"))

        self.assertEqual(packet.payload["status"], "fail")
        self.assertIn("TestCheckoutFlow", packet.payload["failing_tests"])

    def test_cargo_log_keeps_failing_test_and_panic_line(self):
        packet = self.assert_compacts(self.read_log("cargo-fail.txt"))

        self.assertEqual(packet.payload["status"], "fail")
        self.assertIn(
            "pricing::tests::rejects_negative_total",
            packet.payload["failing_tests"],
        )
        self.assertTrue(
            any("panicked at" in line for line in packet.payload["error_lines"])
        )
        self.assertTrue(
            any(line.startswith("test result: FAILED") for line in packet.payload["summary_lines"])
        )

    def test_tsc_log_keeps_error_lines_and_files(self):
        packet = compact_command_output(self.read_log("tsc-fail.txt"))

        self.assertEqual(packet.payload["status"], "fail")
        self.assertTrue(
            any("error TS2339" in line for line in packet.payload["error_lines"])
        )
        self.assertIn("src/components/CartSummary.tsx", packet.payload["primary_files"])

    def test_short_tsc_log_is_not_worth_trimming(self):
        from flowtrim.trim import trim_text

        decision = trim_text(self.read_log("tsc-fail.txt"))

        self.assertEqual(decision.action, "raw")
        self.assertIn("no token savings", decision.reason)

    def test_npm_err_log_keeps_error_lines(self):
        packet = self.assert_compacts(self.read_log("npm-err.txt"))

        self.assertEqual(packet.payload["status"], "fail")
        self.assertTrue(
            any("npm ERR!" in line for line in packet.payload["error_lines"])
        )


if __name__ == "__main__":
    unittest.main()
