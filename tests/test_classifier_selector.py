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

    def test_exact_evidence_always_chooses_raw(self):
        raw = result("raw", Lane.EXACT_EVIDENCE, 100)
        compact = result("summary", Lane.EXACT_EVIDENCE, 25)

        selected = select_best_method(Lane.EXACT_EVIDENCE, [raw, compact])

        self.assertEqual(selected, raw)


if __name__ == "__main__":
    unittest.main()
