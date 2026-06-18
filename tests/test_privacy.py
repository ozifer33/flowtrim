import py_compile
import tempfile
import unittest
from pathlib import Path

from flowtrim.privacy import scan_text


class PrivacyTest(unittest.TestCase):
    def test_flags_private_home_path(self):
        private_path = "/".join(("", "Users", "sample", "Documents", "Work", "private"))
        findings = scan_text("open " + private_path)
        self.assertIn("private-path", findings)

    def test_flags_env_secret_shape(self):
        env_name = "_".join(("OPENAI", "API", "KEY"))
        value = "-".join(("sk", "test", "secret"))
        secret_text = env_name + "=" + value
        findings = scan_text(secret_text)
        self.assertIn("secret-like-env", findings)

    def test_allows_public_fixture_text(self):
        findings = scan_text("synthetic build log: src/app.py passed")
        self.assertEqual(findings, ())

    def test_test_bytecode_does_not_embed_sensitive_shapes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            compiled = Path(tmpdir) / "test_privacy.pyc"
            py_compile.compile(__file__, cfile=str(compiled), doraise=True)
            findings = scan_text(compiled.read_text(errors="ignore"))
        self.assertEqual(findings, ())


if __name__ == "__main__":
    unittest.main()
