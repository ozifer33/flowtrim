import json
import unittest

from flowtrim.models import Lane, MethodResult
from flowtrim.reporter import report_json, report_text


class ReporterTest(unittest.TestCase):
    def test_json_report_is_machine_readable(self):
        result = MethodResult("rtk", Lane.COMMAND_OUTPUT, 40, 100, 12, True, "measured")
        data = json.loads(report_json(result))
        self.assertEqual(data["schema"], "flowtrim-decision/v1")
        self.assertEqual(data["selected_method"], "rtk")
        self.assertEqual(data["lane"], "command-output")

    def test_text_report_is_compact(self):
        result = MethodResult("raw", Lane.EXACT_EVIDENCE, 100, 100, 5, True, "exact")
        text = report_text(result)
        self.assertIn("FlowTrim decision:", text)
        self.assertIn("Selected method: raw", text)
        self.assertLess(len(text.splitlines()), 12)


if __name__ == "__main__":
    unittest.main()
