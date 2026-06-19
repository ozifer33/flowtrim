import hashlib
import time
import unittest

from flowtrim.adapters import (
    HeadroomAdapter,
    PonytailLens,
    RTKAdapter,
    RawAdapter,
    hash_text,
    median_measure,
)
from flowtrim.benchmark import BenchmarkStatus, MethodMeasurement
from flowtrim.models import Lane


class AdapterTest(unittest.TestCase):
    def test_hash_text_returns_short_sha256_digest(self):
        self.assertEqual(
            hash_text("fixture output"),
            hashlib.sha256(b"fixture output").hexdigest()[:12],
        )

    def test_median_measure_reports_repeated_wall_time_and_timeout(self):
        values = iter(("first", "second", "third"))

        result = median_measure(lambda: next(values), repeat_count=3, timeout_ms=1000)

        self.assertEqual(result.value, "third")
        self.assertEqual(result.repeat_count, 3)
        self.assertFalse(result.timeout)
        self.assertGreaterEqual(result.wall_time_ms, 0)

        slow = median_measure(lambda: time.sleep(0.003), repeat_count=3, timeout_ms=1)

        self.assertEqual(slow.repeat_count, 3)
        self.assertTrue(slow.timeout)
        self.assertGreaterEqual(slow.wall_time_ms, 1)

    def test_raw_adapter_returns_measurement_hash_without_raw_output(self):
        text = "warning: src/example.py failed with TEST_ERROR"

        measurement = RawAdapter().measure(text, Lane.COMMAND_OUTPUT, repeat_count=3)

        self.assertIsInstance(measurement, MethodMeasurement)
        self.assertEqual(measurement.method, "raw")
        self.assertEqual(measurement.status, BenchmarkStatus.OK)
        self.assertEqual(measurement.tokens, 12)
        self.assertGreaterEqual(measurement.wall_time_ms, 0)
        self.assertLess(measurement.wall_time_ms, 10)
        self.assertFalse(measurement.timeout)
        self.assertEqual(measurement.repeat_count, 3)
        self.assertTrue(measurement.guard_passed)
        self.assertEqual(measurement.payload, {"content_hash": hash_text(text)})
        self.assertNotIn("raw_output", measurement.payload)

    def test_rtk_adapter_skips_when_executable_is_not_found(self):
        measurement = RTKAdapter(executable="definitely-missing-rtk").measure(
            "large output",
            Lane.COMMAND_OUTPUT,
        )

        self.assertEqual(measurement.method, "rtk")
        self.assertEqual(measurement.status, BenchmarkStatus.SKIPPED)
        self.assertEqual(measurement.tokens, 0)
        self.assertFalse(measurement.timeout)
        self.assertFalse(measurement.guard_passed)
        self.assertIn("not found", measurement.reason)

    def test_rtk_adapter_uses_injected_runner_without_rewriting_shell_commands(self):
        calls = []

        def runner(input_text):
            calls.append(input_text)
            return "src/example.py\nTEST_ERROR\ncompact summary"

        measurement = RTKAdapter(runner=runner).measure(
            "src/example.py\nTEST_ERROR\nlong noisy details",
            Lane.COMMAND_OUTPUT,
            must_preserve=("src/example.py", "TEST_ERROR"),
            repeat_count=3,
        )

        self.assertEqual(calls, ["src/example.py\nTEST_ERROR\nlong noisy details"] * 3)
        self.assertEqual(measurement.status, BenchmarkStatus.OK)
        self.assertEqual(measurement.tokens, 11)
        self.assertFalse(measurement.timeout)
        self.assertEqual(measurement.repeat_count, 3)
        self.assertTrue(measurement.guard_passed)
        self.assertEqual(
            measurement.payload,
            {"content_hash": hash_text("src/example.py\nTEST_ERROR\ncompact summary")},
        )
        self.assertNotIn("command", measurement.payload)

    def test_rtk_adapter_reports_guard_failure_for_missing_must_preserve_items(self):
        measurement = RTKAdapter(runner=lambda text: "compact summary").measure(
            "src/example.py\nTEST_ERROR\nlong noisy details",
            Lane.COMMAND_OUTPUT,
            must_preserve=("src/example.py", "TEST_ERROR"),
        )

        self.assertEqual(measurement.status, BenchmarkStatus.OK)
        self.assertFalse(measurement.guard_passed)
        self.assertIn("missing required items", measurement.reason)

    def test_headroom_adapter_skips_when_unavailable_without_version_checks(self):
        version_calls = []

        measurement = HeadroomAdapter(
            executable="headroom",
            which=lambda executable: None,
            version_runner=lambda executable: version_calls.append(executable),
        ).measure("large context", Lane.LONG_CONTEXT)

        self.assertEqual(version_calls, [])
        self.assertEqual(measurement.method, "headroom-direct")
        self.assertEqual(measurement.status, BenchmarkStatus.SKIPPED)
        self.assertFalse(measurement.guard_passed)
        self.assertIn("not found", measurement.reason)

    def test_headroom_adapter_only_checks_version_when_available(self):
        version_calls = []

        def version_runner(executable):
            version_calls.append(executable)
            return "headroom 1.2.3"

        measurement = HeadroomAdapter(
            executable="headroom",
            which=lambda executable: "/usr/local/bin/headroom",
            version_runner=version_runner,
        ).measure("large context", Lane.LONG_CONTEXT)

        self.assertEqual(version_calls, ["/usr/local/bin/headroom"])
        self.assertEqual(measurement.status, BenchmarkStatus.SKIPPED)
        self.assertEqual(measurement.payload, {"version": "headroom 1.2.3"})
        self.assertIn("safe adapter", measurement.reason)

    def test_headroom_adapter_uses_injected_direct_runner_when_available(self):
        calls = []

        def runner(input_text):
            calls.append(input_text)
            return "trace-demo-001 job-demo-17 source:demo-trace-001 compact failure facts"

        measurement = HeadroomAdapter(
            which=lambda executable: "/usr/local/bin/headroom",
            version_runner=lambda executable: "headroom 1.2.3",
            runner=runner,
        ).measure(
            "trace-demo-001 job-demo-17 source:demo-trace-001 long noisy context",
            Lane.LONG_CONTEXT,
            must_preserve=("trace-demo-001", "job-demo-17", "source:demo-trace-001"),
            repeat_count=3,
        )

        self.assertEqual(calls, ["trace-demo-001 job-demo-17 source:demo-trace-001 long noisy context"] * 3)
        self.assertEqual(measurement.method, "headroom-direct")
        self.assertEqual(measurement.status, BenchmarkStatus.OK)
        self.assertTrue(measurement.guard_passed)
        self.assertEqual(measurement.payload["version"], "headroom 1.2.3")
        self.assertIn("sanitized_snippet", measurement.payload)

    def test_headroom_adapter_reports_guard_failure_for_missing_direct_items(self):
        measurement = HeadroomAdapter(
            which=lambda executable: "/usr/local/bin/headroom",
            runner=lambda text: "compact summary missing the source id",
        ).measure(
            "trace-demo-001 source:demo-trace-001 long noisy context",
            Lane.LONG_CONTEXT,
            must_preserve=("trace-demo-001", "source:demo-trace-001"),
        )

        self.assertEqual(measurement.status, BenchmarkStatus.OK)
        self.assertFalse(measurement.guard_passed)
        self.assertIn("missing required items", measurement.reason)

    def test_headroom_adapter_rejects_proxy_wrap_or_mcp_direct_output(self):
        unsafe_outputs = [
            "headroom proxy --port 8787",
            "headroom wrap codex",
            "headroom mcp install",
            "headroom learn --apply",
        ]
        for output in unsafe_outputs:
            with self.subTest(output=output):
                measurement = HeadroomAdapter(
                    which=lambda executable: "/usr/local/bin/headroom",
                    runner=lambda text, output=output: output,
                ).measure("trace-demo-001 long noisy context", Lane.LONG_CONTEXT)

                self.assertFalse(measurement.guard_passed)
                self.assertIn("forbidden headroom mode", measurement.reason)

    def test_ponytail_lens_returns_safe_delete_list_payload(self):
        measurement = PonytailLens().analyze(
            "\n".join(
                [
                    "duplicate helper convert_user_id",
                    "over-abstract wrapper UserIdFormatter",
                    "ordinary implementation line",
                ]
            )
        )

        self.assertEqual(measurement.method, "ponytail-lens")
        self.assertEqual(measurement.status, BenchmarkStatus.OK)
        self.assertTrue(measurement.guard_passed)
        self.assertIn("delete_items", measurement.payload)
        self.assertGreaterEqual(len(measurement.payload["delete_items"]), 2)
        self.assertEqual(
            set(measurement.payload["delete_items"][0]),
            {
                "item",
                "severity",
                "rationale",
                "estimated_loc_delta",
                "requirement_affected",
                "test_surface_affected",
                "must_keep_violation",
            },
        )
        self.assertFalse(measurement.payload["must_keep_violation"])
        self.assertTrue(measurement.payload["requirements_preserved"])
        self.assertTrue(measurement.payload["test_surface_preserved"])
        self.assertEqual(
            measurement.payload["delete_items"][0]["requirement_affected"],
            "none",
        )
        self.assertEqual(
            measurement.payload["delete_items"][0]["test_surface_affected"],
            "none",
        )

    def test_ponytail_lens_flags_must_keep_and_test_surface_violations(self):
        measurement = PonytailLens().analyze(
            "\n".join(
                [
                    "delete duplicate helper required_parser",
                    "remove wrapper test_required_parser",
                ]
            ),
            must_keep=("required_parser",),
            tests=("test_required_parser",),
        )

        items = measurement.payload["delete_items"]
        self.assertTrue(items[0]["must_keep_violation"])
        self.assertEqual(items[0]["requirement_affected"], "required_parser")
        self.assertTrue(items[1]["must_keep_violation"])
        self.assertEqual(items[1]["test_surface_affected"], "test_required_parser")
        self.assertTrue(measurement.payload["must_keep_violation"])
        self.assertFalse(measurement.payload["requirements_preserved"])
        self.assertFalse(measurement.payload["test_surface_preserved"])


if __name__ == "__main__":
    unittest.main()
