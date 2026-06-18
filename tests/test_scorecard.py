import unittest

from flowtrim.scorecard import DecisionLabel, ScorecardResult, compare_token_methods


class ScorecardTest(unittest.TestCase):
    def test_native_win_requires_primary_score_and_all_guards(self):
        result = compare_token_methods(
            raw_tokens=100,
            native_tokens=40,
            baseline_tokens=55,
            native_guard_passed=True,
            baseline_guard_passed=True,
            native_wall_time_ms=8,
            baseline_wall_time_ms=10,
            wall_time_budget_ms=250,
        )

        self.assertEqual(result.label, DecisionLabel.NATIVE_WIN)
        self.assertEqual(result.primary_delta, 60)
        self.assertEqual(result.selected_method, "flowtrim-native-command")

    def test_baseline_win_when_baseline_is_safer_or_smaller(self):
        result = compare_token_methods(
            raw_tokens=100,
            native_tokens=60,
            baseline_tokens=40,
            native_guard_passed=True,
            baseline_guard_passed=True,
            native_wall_time_ms=8,
            baseline_wall_time_ms=10,
            wall_time_budget_ms=250,
        )

        self.assertEqual(result.label, DecisionLabel.BASELINE_WIN)
        self.assertEqual(result.selected_method, "rtk")

    def test_raw_win_for_short_output_or_over_budget_candidates(self):
        short = compare_token_methods(
            raw_tokens=3,
            native_tokens=1,
            baseline_tokens=1,
            native_guard_passed=True,
            baseline_guard_passed=True,
            native_wall_time_ms=8,
            baseline_wall_time_ms=10,
            wall_time_budget_ms=250,
        )
        slow = compare_token_methods(
            raw_tokens=100,
            native_tokens=10,
            baseline_tokens=20,
            native_guard_passed=True,
            baseline_guard_passed=True,
            native_wall_time_ms=999,
            baseline_wall_time_ms=999,
            wall_time_budget_ms=250,
        )

        self.assertEqual(short.label, DecisionLabel.RAW_WIN)
        self.assertEqual(slow.label, DecisionLabel.RAW_WIN)

    def test_insufficient_evidence_when_smaller_candidate_fails_guard(self):
        result = compare_token_methods(
            raw_tokens=100,
            native_tokens=10,
            baseline_tokens=20,
            native_guard_passed=False,
            baseline_guard_passed=False,
            native_wall_time_ms=8,
            baseline_wall_time_ms=10,
            wall_time_budget_ms=250,
        )

        self.assertEqual(result.label, DecisionLabel.INSUFFICIENT_EVIDENCE)
        self.assertIsNone(result.selected_method)
        self.assertIsInstance(result, ScorecardResult)


if __name__ == "__main__":
    unittest.main()
