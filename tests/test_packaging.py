import tomllib
import unittest
from pathlib import Path

from flowtrim.benchmark import DEFAULT_FIXTURES_ROOT
from flowtrim.public_corpus import DEFAULT_PUBLIC_CORPUS_MANIFEST


ROOT = Path(__file__).resolve().parents[1]


class PackagingTest(unittest.TestCase):
    def test_pyproject_declares_public_alpha_console_scripts(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        scripts = data["project"]["scripts"]
        self.assertEqual(scripts["flowtrim-benchmark"], "flowtrim.cli.benchmark:main")
        self.assertEqual(scripts["flowtrim-classify"], "flowtrim.cli.orchestrator:main")
        self.assertEqual(scripts["flowtrim-run"], "flowtrim.cli.run:main")
        self.assertEqual(scripts["flowtrim-trim"], "flowtrim.cli.trim:main")

    def test_package_declares_benchmark_resource_data(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        package_data = data["tool"]["setuptools"]["package-data"]["flowtrim"]
        self.assertIn("fixtures/**/*.txt", package_data)
        self.assertIn("fixtures/**/*.json", package_data)
        self.assertIn("fixtures/**/*.md", package_data)
        self.assertIn("public-corpus/*.json", package_data)

    def test_default_packaged_resources_are_readable(self):
        self.assertTrue((DEFAULT_FIXTURES_ROOT / "logs" / "noisy-build-pass.txt").is_file())
        self.assertTrue(DEFAULT_PUBLIC_CORPUS_MANIFEST.is_file())


if __name__ == "__main__":
    unittest.main()
