import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from flowtrim.benchmark import report_to_json, run_suite
from flowtrim.privacy import scan_text
from flowtrim.public_corpus import (
    DEFAULT_PUBLIC_CORPUS_MANIFEST,
    audit_public_corpus_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "flowtrim" / "scripts" / "flowtrim_benchmark.py"
REQUIRED_PUBLIC_DOCS = (
    "QUICKSTART.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "docs/install.md",
    "docs/assets/flowtrim-public-alpha-benchmark.svg",
    "benchmarks/results/2026-06-19-public-alpha.md",
)


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "src"},
    )


class PublicReadinessTest(unittest.TestCase):
    def test_public_docs_and_pyproject_metadata_are_present(self):
        for name in REQUIRED_PUBLIC_DOCS:
            with self.subTest(name=name):
                self.assertTrue((ROOT / name).is_file())

        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = data["project"]
        self.assertIn("urls", project)
        self.assertIn("Homepage", project["urls"])
        self.assertIn("Repository", project["urls"])
        self.assertIn("Issue Tracker", project["urls"])
        self.assertIn("keywords", project)
        self.assertIn("classifiers", project)
        self.assertIn("flowtrim-benchmark", project["scripts"])
        self.assertIn("flowtrim-classify", project["scripts"])

        package = ROOT / "package.json"
        self.assertTrue(package.is_file())
        package_data = json.loads(package.read_text(encoding="utf-8"))
        self.assertEqual(package_data["name"], "flowtrim-skill-install")
        self.assertIn("flowtrim-skill-install", package_data["bin"])

    def test_readme_is_short_public_landing_page_with_scoreboard(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        line_count = len(readme.splitlines())

        self.assertLessEqual(line_count, 150)
        self.assertIn("docs/assets/flowtrim-public-alpha-benchmark.svg", readme)
        self.assertIn("| Profile | Cases | Token wins | Tokens saved | Raw refusals | Code-lens wins | Claim boundary |", readme)
        self.assertIn("docs/install.md", readme)
        self.assertIn("No global benchmark claim", readme)
        self.assertNotIn("flowtrim-benchmark suite --profile aql-vault-readonly", readme)
        self.assertNotIn("flowtrim-benchmark suite --profile work-code-readonly", readme)

    def test_install_docs_have_native_and_convenience_paths(self):
        text = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")

        self.assertIn("/plugin marketplace add ozifer33/flowtrim", text)
        self.assertIn("/plugin install flowtrim@flowtrim", text)
        self.assertIn("npx github:ozifer33/flowtrim --agent codex --scope user", text)
        self.assertIn(".agents/skills", text)
        self.assertIn(".github/skills", text)
        self.assertIn("convenience installer", text)
        self.assertIn("needs verification", text)

    def test_docs_check_accepts_repo_docs(self):
        result = run_cli("docs-check", "--format", "json")

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["schema"], "flowtrim-docs-check/v1")
        self.assertTrue(data["valid"])
        self.assertEqual(data["findings"], [])

    def test_docs_check_rejects_source_checkout_command_outside_fallback_without_path_leak(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "README.md").write_text(
                "# Demo\n\n```bash\nPYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py abcd\n```\n",
                encoding="utf-8",
            )
            for name in REQUIRED_PUBLIC_DOCS:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# " + name + "\n", encoding="utf-8")
            skill_root = root / "skills" / "flowtrim"
            skill_root.mkdir(parents=True)
            (skill_root / "SKILL.md").write_text(
                "---\nname: flowtrim\ndescription: demo\n---\n# FlowTrim\n\n## Commands\n",
                encoding="utf-8",
            )

            result = run_cli("docs-check", "--root", str(root), "--format", "json")

        self.assertNotEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["schema"], "flowtrim-docs-check/v1")
        self.assertFalse(data["valid"])
        self.assertTrue(data["findings"])
        self.assertEqual(data["findings"][0]["target"], "docs")
        self.assertNotIn(str(root), result.stdout)

    def test_public_playground_profile_has_adoption_cases_without_private_output(self):
        report = run_suite("public-playground-readonly")
        text = report_to_json(report)
        data = json.loads(text)
        case_ids = {case["case_id"] for case in data["cases"]}

        self.assertEqual(data["profile"], "public-playground-readonly")
        self.assertGreaterEqual(data["metric_totals"]["token-bearing"]["wins"], 1)
        self.assertGreaterEqual(data["metric_totals"]["refusal-correctness"]["correct_refusals"], 1)
        self.assertGreaterEqual(data["metric_totals"]["code-lens"]["cases"], 1)
        self.assertIn("public-playground/nestjs-jest-command", case_ids)
        self.assertIn("public-playground/vite-large-chunk-command", case_ids)
        self.assertIn("public-playground/vue-type-check-command", case_ids)
        self.assertIn("public-playground/dirty-before-unchanged-command", case_ids)
        self.assertIn("public-playground/ticket-churn-command", case_ids)
        self.assertTrue(any("/control-" in case_id for case_id in case_ids))
        self.assertTrue(data["runtime_changes"])
        self.assertFalse(data["runtime_changes"]["unapproved_filesystem_writes"])
        self.assertTrue(data["runtime_changes"]["preexisting_dirty_worktree"])
        self.assertFalse(data["runtime_changes"]["post_status_changed"])
        self.assertEqual(scan_text(text), ())
        self.assertNotIn("pytest_public_failure", text)
        self.assertNotIn("normalizePublicPlaygroundValue", text)

    def test_public_corpus_audit_accepts_valid_manifest_as_aggregate_only(self):
        payload = audit_public_corpus_manifest(DEFAULT_PUBLIC_CORPUS_MANIFEST)
        text = json.dumps(payload, sort_keys=True)

        self.assertEqual(payload["schema"], "flowtrim-public-corpus-audit/v1")
        self.assertTrue(payload["valid"])
        self.assertGreaterEqual(payload["repo_count"], 1)
        self.assertIn("language_families", payload)
        self.assertIn("licenses", payload)
        self.assertEqual(payload["findings"], [])
        self.assertEqual(scan_text(text), ())
        self.assertNotIn("github.com", text)

    def test_public_corpus_audit_rejects_unpinned_or_private_manifest_without_leak(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "flowtrim-public-corpus/v1",
                        "repos": [
                            {
                                "url": "/tmp/private/repo",
                                "branch": "main",
                                "pinned_commit": "main",
                                "license": "",
                                "language_family": "python",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = audit_public_corpus_manifest(manifest)
            text = json.dumps(payload, sort_keys=True)

        self.assertFalse(payload["valid"])
        self.assertTrue(payload["findings"])
        self.assertEqual(payload["findings"][0]["target"], "repo-001")
        self.assertNotIn(str(root), text)
        self.assertNotIn("/tmp/private/repo", text)


if __name__ == "__main__":
    unittest.main()
