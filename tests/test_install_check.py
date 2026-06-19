import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowtrim.install_check import install_check_payload, install_check_to_markdown, _run
from flowtrim.privacy import scan_text


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "flowtrim" / "scripts" / "flowtrim_benchmark.py"


def run_cli(*args):
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


class InstallCheckTest(unittest.TestCase):
    def test_install_check_default_is_aggregate_and_privacy_safe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_cli(
                "install-check",
                "--tmp-root",
                tmpdir,
                "--format",
                "json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], "flowtrim-install-check/v1")
        self.assertTrue(payload["valid"])
        self.assertEqual(scan_text(result.stdout), ())
        self.assertNotIn(tmpdir, result.stdout)
        self.assertNotIn(str(ROOT), result.stdout)

        by_method = {item["method"]: item for item in payload["checks"]}
        self.assertEqual(by_method["skill-source-shape"]["status"], "passed")
        self.assertEqual(by_method["node-project-install"]["status"], "passed")
        self.assertEqual(by_method["shell-project-install"]["status"], "passed")
        self.assertEqual(by_method["clean-clone-install"]["status"], "skipped-neutral")
        self.assertEqual(by_method["npx-github-install"]["status"], "skipped-neutral")
        self.assertEqual(by_method["gh-skill-install"]["status"], "skipped-neutral")
        self.assertEqual(by_method["claude-plugin-install"]["status"], "skipped-neutral")
        self.assertGreaterEqual(by_method["node-project-install"]["copied_file_count"], 4)
        self.assertEqual(payload["privacy_findings"], [])

    def test_install_check_markdown_omits_paths_and_raw_logs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = install_check_payload(ROOT, tmp_root=tmpdir)
            text = install_check_to_markdown(payload)

        self.assertIn("# FlowTrim Install Check", text)
        self.assertIn("node-project-install", text)
        self.assertNotIn(str(ROOT), text)
        self.assertNotIn(tmpdir, text)
        self.assertEqual(scan_text(text), ())

    def test_install_check_reports_external_tools_as_skipped_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = install_check_payload(
                ROOT,
                tmp_root=tmpdir,
                run_npx=True,
                run_gh_skill=True,
                run_claude_plugin=True,
                tool_overrides={
                    "node": None,
                    "npx": None,
                    "gh": None,
                    "claude": None,
                    "pwsh": None,
                },
            )

        by_method = {item["method"]: item for item in payload["checks"]}
        self.assertEqual(by_method["npx-github-install"]["status"], "skipped-neutral")
        self.assertEqual(by_method["gh-skill-install"]["status"], "skipped-neutral")
        self.assertEqual(by_method["claude-plugin-install"]["status"], "skipped-neutral")
        self.assertEqual(by_method["powershell-project-install"]["status"], "skipped-neutral")
        self.assertNotIn("verified", by_method["npx-github-install"]["claim_allowed"])

    def test_install_check_rejects_private_output_in_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = install_check_payload(ROOT, tmp_root=tmpdir)
            payload["checks"][0]["evidence"] = "/" + "Users" + "/demo/private/path"

            with self.assertRaises(ValueError):
                install_check_to_markdown(payload)

    def test_install_check_cli_supports_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_cli(
                "install-check",
                "--tmp-root",
                tmpdir,
                "--format",
                "markdown",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# FlowTrim Install Check", result.stdout)
        self.assertNotIn(tmpdir, result.stdout)

    def test_install_check_does_not_write_inside_repo_when_tmp_root_collides(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "skills" / "flowtrim" / "references").mkdir(parents=True)
            (root / "skills" / "flowtrim" / "scripts").mkdir(parents=True)
            (root / "skills" / "flowtrim" / "agents").mkdir(parents=True)
            (root / "skills" / "flowtrim" / "SKILL.md").write_text("demo", encoding="utf-8")
            (root / "skills" / "flowtrim" / "references" / "lane-policy.md").write_text("demo", encoding="utf-8")
            (root / "skills" / "flowtrim" / "scripts" / "flowtrim_benchmark.py").write_text("demo", encoding="utf-8")
            (root / "skills" / "flowtrim" / "agents" / "openai.yaml").write_text("demo", encoding="utf-8")
            (root / ".claude-plugin").mkdir()
            (root / ".claude-plugin" / "marketplace.json").write_text('{"name":"flowtrim"}', encoding="utf-8")
            (root / ".claude-plugin" / "plugin.json").write_text(
                '{"name":"flowtrim","skills":["./skills/flowtrim"]}',
                encoding="utf-8",
            )

            payload = install_check_payload(
                root,
                tmp_root=root,
                tool_overrides={"node": None, "pwsh": None},
            )

            self.assertTrue(payload["valid"])
            self.assertFalse((root / "node-project").exists())
            self.assertFalse((root / "shell-project").exists())

    def test_install_check_subprocess_timeout_does_not_raise(self):
        result = _run(
            [sys.executable, "-c", "import time; time.sleep(1)"],
            timeout=0.01,
        )

        self.assertEqual(result.returncode, 124)
        self.assertIn("timeout", result.stderr)


if __name__ == "__main__":
    unittest.main()
