import unittest

from flowtrim.privacy import scan_text


class PrivacyTest(unittest.TestCase):
    def test_flags_private_home_path(self):
        private_path = "/Users/" + "sample" + "/Documents/Work/private"
        findings = scan_text("open " + private_path)
        self.assertIn("private-path", findings)

    def test_flags_env_secret_shape(self):
        secret_text = "OPENAI_API_KEY" + "=" + "sk-test-secret"
        findings = scan_text(secret_text)
        self.assertIn("secret-like-env", findings)

    def test_allows_public_fixture_text(self):
        findings = scan_text("synthetic build log: src/app.py passed")
        self.assertEqual(findings, ())


if __name__ == "__main__":
    unittest.main()
