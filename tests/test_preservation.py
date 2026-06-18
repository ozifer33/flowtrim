import unittest

from flowtrim.preservation import PreservationReport, check_preservation


class PreservationTest(unittest.TestCase):
    def test_preserves_required_items(self):
        report = check_preservation(
            original="failed at /app/src/main.py with TEST_ERROR",
            candidate="/app/src/main.py TEST_ERROR",
            must_preserve=("/app/src/main.py", "TEST_ERROR"),
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.missing, ())

    def test_fails_when_required_item_is_missing(self):
        report = check_preservation(
            original="see https://example.test and /tmp/file.txt",
            candidate="see compact summary",
            must_preserve=("https://example.test", "/tmp/file.txt"),
        )
        self.assertFalse(report.passed)
        self.assertEqual(report.missing, ("https://example.test", "/tmp/file.txt"))

    def test_report_is_stable_text(self):
        report = PreservationReport(passed=False, missing=("A", "B"))
        self.assertEqual(report.reason, "missing required items: A, B")


if __name__ == "__main__":
    unittest.main()
