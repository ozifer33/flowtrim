import json
import tempfile
import unittest
from pathlib import Path

from flowtrim.benchmark import BenchmarkStatus, report_to_json, run_suite
from flowtrim.compare import compare_reports, compare_reports_to_markdown
from flowtrim.privacy import scan_text


def write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class CompareReportTest(unittest.TestCase):
    def test_compare_report_rejects_schema_profile_and_case_mismatch(self):
        baseline = json.loads(report_to_json(run_suite("synthetic-heavy")))
        candidate = json.loads(json.dumps(baseline))

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bad_schema = json.loads(json.dumps(candidate))
            bad_schema["schema"] = "other"
            with self.assertRaisesRegex(ValueError, "schema mismatch"):
                compare_reports(
                    write_json(root / "baseline.json", baseline),
                    write_json(root / "candidate.json", bad_schema),
                    focus="headroom-direct",
                )

            bad_profile = json.loads(json.dumps(candidate))
            bad_profile["profile"] = "other-profile"
            with self.assertRaisesRegex(ValueError, "profile mismatch"):
                compare_reports(
                    write_json(root / "baseline.json", baseline),
                    write_json(root / "candidate.json", bad_profile),
                    focus="headroom-direct",
                )

            bad_cases = json.loads(json.dumps(candidate))
            bad_cases["cases"] = bad_cases["cases"][:-1]
            with self.assertRaisesRegex(ValueError, "case id mismatch"):
                compare_reports(
                    write_json(root / "baseline.json", baseline),
                    write_json(root / "candidate.json", bad_cases),
                    focus="headroom-direct",
                )

            non_json = root / "not-json.txt"
            non_json.write_text("not json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid report json"):
                compare_reports(
                    write_json(root / "baseline.json", baseline),
                    non_json,
                    focus="headroom-direct",
                )

    def test_compare_report_summarizes_headroom_without_leaking_payloads(self):
        baseline = json.loads(report_to_json(run_suite("synthetic-heavy")))
        candidate = json.loads(json.dumps(baseline))
        private_payload = "/" + "Users" + "/private/raw/source line must not leak"
        safe_raw_tokens = None
        unsafe_raw_tokens = None
        for case in candidate["cases"]:
            if case["case_id"] == "command-output/noisy-build-pass":
                raw = next(method for method in case["methods"] if method["method"] == "raw")
                safe_raw_tokens = raw["tokens"]
                raw["status"] = BenchmarkStatus.OK.value
                case["selected_method"] = "headroom-direct"
                case["winner"] = "headroom-direct"
                case["counts_as_claim"] = True
                case["decision_reason"] = "lower-token-safe"
                case["methods"].append(
                    {
                        "method": "headroom-direct",
                        "status": BenchmarkStatus.SELECTED.value,
                        "tokens": 3,
                        "wall_time_ms": 1,
                        "timeout": False,
                        "repeat_count": 3,
                        "guard_passed": True,
                        "reason": None,
                        "payload": {
                            "sanitized_snippet": private_payload,
                            "content_hash": "abc123",
                        },
                    }
                )
            elif case["case_id"] == "command-output/noisy-build-fail":
                raw = next(method for method in case["methods"] if method["method"] == "raw")
                unsafe_raw_tokens = raw["tokens"]
                case["methods"].append(
                    {
                        "method": "headroom-direct",
                        "status": BenchmarkStatus.OK.value,
                        "tokens": 1,
                        "wall_time_ms": 1,
                        "timeout": False,
                        "repeat_count": 3,
                        "guard_passed": False,
                        "reason": "missing required items",
                        "payload": {"content_hash": "guardfail"},
                    }
                )
            elif case["lane"] == "command-output":
                case["methods"].append(
                    {
                        "method": "headroom-direct",
                        "status": BenchmarkStatus.SKIPPED.value,
                        "tokens": 0,
                        "wall_time_ms": 0,
                        "timeout": False,
                        "repeat_count": 0,
                        "guard_passed": False,
                        "reason": "not installed",
                        "payload": None,
                    }
                )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            summary = compare_reports(
                write_json(root / "baseline.json", baseline),
                write_json(root / "candidate.json", candidate),
                focus="headroom-direct",
            )
            markdown = compare_reports_to_markdown(summary)

        self.assertEqual(summary["schema"], "flowtrim-comparison/v1")
        self.assertEqual(summary["profile"], "synthetic-heavy")
        self.assertEqual(summary["focus"], "headroom-direct")
        self.assertGreaterEqual(summary["cases_matched"], 1)
        self.assertEqual(summary["focus_totals"]["selected"], 1)
        self.assertEqual(summary["winner_totals"]["headroom-direct"], 1)
        self.assertIn("Headroom", markdown)
        self.assertIn("headroom-direct", markdown)
        self.assertNotIn("/" + "Users", json.dumps(summary))
        self.assertNotIn("raw/source", markdown)
        self.assertEqual(summary["focus_totals"]["measured"], 2)
        self.assertEqual(summary["focus_totals"]["guard_failed"], 1)
        self.assertEqual(summary["token_delta"]["focus_vs_raw"], safe_raw_tokens - 3)
        self.assertIsNotNone(unsafe_raw_tokens)
        self.assertEqual(scan_text(json.dumps(summary)), ())
        self.assertEqual(scan_text(markdown), ())


if __name__ == "__main__":
    unittest.main()
