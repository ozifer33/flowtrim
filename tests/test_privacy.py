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

    def test_flags_any_private_home_path(self):
        private_path = "/".join(("", "Users", "sample", "project", "private.txt"))
        findings = scan_text("open " + private_path)
        self.assertIn("private-path", findings)

    def test_flags_relative_sensitive_paths(self):
        codex_path = "/".join(("." + "codex", "config.toml"))
        work_path = "/".join(("Documents", "Work", "client"))
        env_file = "." + "env"

        self.assertIn("codex-path", scan_text("open " + codex_path))
        self.assertIn("work-path", scan_text("open " + work_path))
        self.assertIn("env-file", scan_text("read " + env_file))

    def test_flags_explicit_relative_sensitive_paths(self):
        codex_path = "/".join(("..", "." + "codex", "config.toml"))
        work_path = "/".join((".", "Documents", "Work", "client"))
        env_file = "/".join((".", "." + "env"))

        self.assertIn("codex-path", scan_text("open " + codex_path))
        self.assertIn("work-path", scan_text("open " + work_path))
        self.assertIn("env-file", scan_text("cat " + env_file))

    def test_flags_env_secret_shape(self):
        env_name = "_".join(("OPENAI", "API", "KEY"))
        value = "-".join(("sk", "test", "secret"))
        secret_text = env_name + "=" + value
        findings = scan_text(secret_text)
        self.assertIn("secret-like-env", findings)

    def test_flags_spaced_and_yaml_like_secret_shape(self):
        env_name = "_".join(("OPENAI", "API", "KEY"))
        spaced = env_name + " = " + "-".join(("sk", "test", "secret"))
        yaml_like = "api_" + "token" + ": " + "demo-secret-value"

        self.assertIn("secret-like-env", scan_text(spaced))
        self.assertIn("secret-like-env", scan_text(yaml_like))

    def test_allows_policy_mentions_without_paths(self):
        codex_name = "." + "codex"
        env_name = "." + "env"
        findings = scan_text(f"Policy mentions {codex_name} and {env_name} without a path.")
        self.assertEqual(findings, ())

    def test_allows_public_fixture_text(self):
        findings = scan_text("synthetic build log: src/app.py passed")
        self.assertEqual(findings, ())

    def test_test_bytecode_does_not_embed_sensitive_shapes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "neutral.py"
            source.write_text("value = 'public fixture text'\n", encoding="utf-8")
            compiled = Path(tmpdir) / "test_privacy.pyc"
            py_compile.compile(str(source), cfile=str(compiled), doraise=True)
            findings = scan_text(compiled.read_text(errors="ignore"))
        self.assertEqual(findings, ())


if __name__ == "__main__":
    unittest.main()
