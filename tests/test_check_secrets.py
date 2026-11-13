"""Offline tests for the commit-time secret check. Every "secret" below is invented."""

import unittest

from tools.check_secrets import scan_added_lines, scan_filenames


def diff(path, *added):
    """Build a tiny git-style diff that adds the given lines to a file."""
    body = "\n".join("+" + line for line in added)
    return f"diff --git a/{path} b/{path}\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(added)} @@\n{body}\n"


class SecretPatternTests(unittest.TestCase):
    def kinds(self, *lines, private=None):
        return [kind for _f, _l, kind in scan_added_lines(diff("app.py", *lines), private)]

    def test_real_looking_keys_are_caught(self):
        self.assertEqual(self.kinds("k = 'gsk_" + "Ab3dE6gH9jK2mN5pQ8sT1vW4yZ7'"), ["Groq API key"])  # secret-scan: fake
        self.assertIn("GitHub token", self.kinds("t = 'ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8'"))  # secret-scan: fake
        self.assertIn("a secret assigned a value", self.kinds('password = "correct-horse-battery-staple"'))  # secret-scan: fake
        self.assertIn("private key block", self.kinds("-----BEGIN RSA PRIVATE KEY-----"))  # secret-scan: fake

    def test_marked_fakes_and_obvious_fakes_are_allowed(self):
        self.assertEqual(self.kinds("k = 'gsk_" + "Ab3dE6gH9jK2mN5pQ8sT1vW4yZ7'  # secret-scan: fake"), [])
        self.assertEqual(self.kinds("k = 'gsk_FAKE0123456789abcdefghijklmnop'"), [])

    def test_blank_placeholders_and_normal_code_are_fine(self):
        self.assertEqual(self.kinds("GROQ_API_KEY=", "api_key = os.getenv('GROQ_API_KEY')", "token = ''"), [])

    def test_personal_email_is_caught_but_safe_ones_are_not(self):
        self.assertEqual(self.kinds("contact: someone.real@school.edu"), ["email address"])  # secret-scan: fake
        self.assertEqual(self.kinds("a@example.com", "123+me@users.noreply.github.com", "noreply@anthropic.com"), [])

    def test_private_words_are_caught_case_insensitively(self):
        found = self.kinds("# written at Some-School.example", private=["some-school"])
        self.assertEqual(len(found), 1)
        self.assertIn("private words", found[0])

    def test_report_never_contains_the_secret_and_gives_the_right_line(self):
        secret = "gsk_" + "Zy9xW8vU7tS6rQ5pO4nM3lK2jI1h"  # secret-scan: fake
        text = diff("src/x.py", "a = 1", "b = 2", f"key = '{secret}'")
        result = scan_added_lines(text)
        self.assertEqual(result, [("src/x.py", 3, "Groq API key")])
        self.assertNotIn(secret, repr(result))


class FileNameTests(unittest.TestCase):
    def test_dangerous_files_are_blocked(self):
        for name in [".env", "sub/.env", ".env.local", "id.pem", "my.key", "talk.wav", "a/b/clip.mp3"]:
            self.assertEqual(len(scan_filenames([name])), 1, name)

    def test_safe_files_pass(self):
        self.assertEqual(scan_filenames([".env.example", "README.md", "trado/main.py", "docs/index.html"]), [])


if __name__ == "__main__":
    unittest.main()
