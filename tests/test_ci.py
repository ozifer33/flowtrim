import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CiWorkflowTest(unittest.TestCase):
    def test_ci_workflow_uses_installed_cli_without_private_or_optional_tool_setup(self):
        workflow = ROOT / ".github" / "workflows" / "ci.yml"

        text = workflow.read_text(encoding="utf-8")

        self.assertIn("python-version: ['3.11', '3.12']", text)
        self.assertIn("python -m pip install -e .", text)
        self.assertIn("python -m pip wheel . -w /tmp/flowtrim-wheelhouse", text)
        self.assertIn("python -m pip install /tmp/flowtrim-wheelhouse/", text)
        self.assertIn("python -m unittest discover -s tests", text)
        self.assertIn("flowtrim-benchmark suite --profile synthetic-heavy", text)
        self.assertIn("flowtrim-benchmark suite --profile public-playground-readonly", text)
        self.assertIn("flowtrim-benchmark privacy-scan --tracked", text)
        self.assertIn("flowtrim-benchmark skill-check --skill-root skills/flowtrim", text)
        self.assertIn("flowtrim-benchmark docs-check --format json", text)
        self.assertIn("flowtrim-benchmark public-corpus audit", text)
        self.assertIn("flowtrim-benchmark claim-check", text)
        self.assertIn("flowtrim-classify", text)
        self.assertNotIn("PYTHONPATH=src", text)
        self.assertNotIn("headroom-ai", text)
        self.assertNotIn("public-corpus prepare", text)
        self.assertNotIn("git clone", text)
        self.assertNotIn("Documents" + "/Work", text)


if __name__ == "__main__":
    unittest.main()
