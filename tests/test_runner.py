import time
import unittest

from flowtrim.models import Lane, LaneTask, MethodResult
from flowtrim.runner import can_run_together, run_parallel


def result(method):
    return MethodResult(
        method=method,
        lane=Lane.COMMAND_OUTPUT,
        tokens=10,
        baseline_tokens=100,
        wall_time_ms=50,
        guard_passed=True,
        reason="test",
    )


class RunnerTest(unittest.TestCase):
    def test_read_only_lane_tasks_can_run_together(self):
        first = LaneTask(
            lane=Lane.COMMAND_OUTPUT,
            name="first",
            read_set=frozenset({"output.log"}),
        )
        second = LaneTask(
            lane=Lane.LONG_CONTEXT,
            name="second",
            read_set=frozenset({"notes.md"}),
        )

        self.assertTrue(can_run_together(first, second))

    def test_mutating_lane_tasks_cannot_run_together_when_write_sets_overlap(self):
        first = LaneTask(
            lane=Lane.COMMAND_OUTPUT,
            name="first",
            read_set=frozenset({"output.log"}),
            write_set=frozenset({"summary.json"}),
        )
        second = LaneTask(
            lane=Lane.LONG_CONTEXT,
            name="second",
            read_set=frozenset({"notes.md"}),
            write_set=frozenset({"summary.json"}),
        )

        self.assertFalse(can_run_together(first, second))

    def test_run_parallel_returns_empty_list_for_empty_runners(self):
        self.assertEqual(run_parallel({}), [])

    def test_run_parallel_returns_results_from_concurrent_runners(self):
        first = result("first")
        second = result("second")

        def first_runner():
            time.sleep(0.05)
            return first

        def second_runner():
            time.sleep(0.05)
            return second

        started_at = time.perf_counter()
        results = run_parallel({"first": first_runner, "second": second_runner})
        elapsed = time.perf_counter() - started_at

        self.assertEqual(results, [first, second])
        self.assertLess(elapsed, 0.09)


if __name__ == "__main__":
    unittest.main()
