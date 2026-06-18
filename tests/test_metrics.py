import unittest

from flowtrim.metrics import estimate_tokens, savings_ratio, lane_primary_metric
from flowtrim.models import Lane, MethodResult


class MetricsTest(unittest.TestCase):
    def test_estimate_tokens_uses_ceil_four_char_rule(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens("abcd"), 1)
        self.assertEqual(estimate_tokens("abcde"), 2)

    def test_savings_ratio_handles_zero_and_positive_baselines(self):
        self.assertEqual(savings_ratio(0, 0), 0.0)
        self.assertEqual(savings_ratio(100, 50), 0.5)
        self.assertEqual(savings_ratio(100, 120), -0.2)

    def test_lane_primary_metric_is_lane_specific(self):
        self.assertEqual(lane_primary_metric(Lane.COMMAND_OUTPUT), "output_tokens")
        self.assertEqual(lane_primary_metric(Lane.LONG_CONTEXT), "input_tokens")
        self.assertEqual(lane_primary_metric(Lane.CODE_GENERATION), "generated_tokens")
        self.assertEqual(lane_primary_metric(Lane.EXACT_EVIDENCE), "raw_required")

    def test_method_result_marks_invalid_when_guard_fails(self):
        result = MethodResult(
            method="rtk",
            lane=Lane.COMMAND_OUTPUT,
            tokens=50,
            baseline_tokens=100,
            wall_time_ms=20,
            guard_passed=False,
            reason="missing required path",
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.savings_vs_baseline, 0.5)


if __name__ == "__main__":
    unittest.main()
