import unittest

from flowtrim.classifier import classify_text
from flowtrim.models import Lane, MethodResult
from flowtrim.selector import select_best_method


def result(method, lane, tokens, guard_passed=True, wall_time_ms=10):
    return MethodResult(
        method=method,
        lane=lane,
        tokens=tokens,
        baseline_tokens=100,
        wall_time_ms=wall_time_ms,
        guard_passed=guard_passed,
        reason="test",
    )


class ClassifierSelectorTest(unittest.TestCase):
    def test_classify_exact_evidence_request(self):
        lanes = classify_text("review this failing diff with exact line numbers")

        self.assertIn(Lane.EXACT_EVIDENCE, lanes)

    def test_classify_failed_stack_trace_as_exact_evidence(self):
        lanes = classify_text("pytest failed with stack trace")

        self.assertIn(Lane.EXACT_EVIDENCE, lanes)

    def test_classify_source_quote_as_exact_evidence(self):
        lanes = classify_text("preserve this source quote exactly")

        self.assertIn(Lane.EXACT_EVIDENCE, lanes)

    def test_classify_short_command_output_as_exact_evidence(self):
        lanes = classify_text("short command output please")

        self.assertIn(Lane.EXACT_EVIDENCE, lanes)

    def test_classify_command_output_request(self):
        lanes = classify_text("npm test produced a long build log")

        self.assertIn(Lane.COMMAND_OUTPUT, lanes)

    def test_select_prefers_valid_lower_token_result_over_raw_for_command_output(self):
        raw = result("raw", Lane.COMMAND_OUTPUT, 100)
        compact = result("summary", Lane.COMMAND_OUTPUT, 25)

        selected = select_best_method(Lane.COMMAND_OUTPUT, [raw, compact])

        self.assertEqual(selected, compact)

    def test_select_rejects_invalid_lower_token_result_and_returns_raw(self):
        raw = result("raw", Lane.COMMAND_OUTPUT, 100)
        invalid = result("summary", Lane.COMMAND_OUTPUT, 25, guard_passed=False)

        selected = select_best_method(Lane.COMMAND_OUTPUT, [raw, invalid])

        self.assertEqual(selected, raw)

    def test_select_rejects_slow_lower_token_result_and_returns_raw(self):
        raw = result("raw", Lane.COMMAND_OUTPUT, 100)
        slow = result("summary", Lane.COMMAND_OUTPUT, 25, wall_time_ms=10_000)

        selected = select_best_method(Lane.COMMAND_OUTPUT, [raw, slow])

        self.assertEqual(selected, raw)

    def test_select_prefers_faster_lower_token_result_over_raw(self):
        raw = result("raw", Lane.COMMAND_OUTPUT, 100)
        compact = result("summary", Lane.COMMAND_OUTPUT, 25, wall_time_ms=200)

        selected = select_best_method(Lane.COMMAND_OUTPUT, [raw, compact])

        self.assertEqual(selected, compact)

    def test_exact_evidence_always_chooses_raw(self):
        raw = result("raw", Lane.EXACT_EVIDENCE, 100)
        compact = result("summary", Lane.EXACT_EVIDENCE, 25)

        selected = select_best_method(Lane.EXACT_EVIDENCE, [raw, compact])

        self.assertEqual(selected, raw)

    def test_exact_evidence_without_same_lane_raw_raises(self):
        other_raw = result("raw", Lane.COMMAND_OUTPUT, 100)
        compact = result("summary", Lane.EXACT_EVIDENCE, 25)

        with self.assertRaisesRegex(ValueError, "requires a raw fallback"):
            select_best_method(Lane.EXACT_EVIDENCE, [other_raw, compact])

    def test_invalid_or_nonmatching_results_without_same_lane_raw_raises(self):
        invalid = result("summary", Lane.COMMAND_OUTPUT, 25, guard_passed=False)
        nonmatching = result("summary", Lane.LONG_CONTEXT, 10)

        with self.assertRaisesRegex(ValueError, "requires a raw fallback"):
            select_best_method(Lane.COMMAND_OUTPUT, [invalid, nonmatching])


if __name__ == "__main__":
    unittest.main()
