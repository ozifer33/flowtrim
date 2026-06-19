import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingTest(unittest.TestCase):
    def test_pyproject_declares_public_alpha_console_scripts(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        scripts = data["project"]["scripts"]
        self.assertEqual(scripts["flowtrim-benchmark"], "flowtrim.cli.benchmark:main")
        self.assertEqual(scripts["flowtrim-classify"], "flowtrim.cli.orchestrator:main")


if __name__ == "__main__":
    unittest.main()
