"""Blocks a commit that contains a secret or private details. The hook in .githooks/pre-commit runs this.

Turn the hook on once per copy of the project:   git config core.hooksPath .githooks

It reads only the lines being added by the commit. It reports the file and line number and the KIND of problem,
and never prints the secret itself. It also reads an optional private list of words to block from
`.git/private-patterns.txt` (one per line; that file is inside .git, so it is never committed or pushed).
Add a fake test value on purpose by putting `secret-scan: fake` on the same line.
"""

import re
import subprocess
import sys
from pathlib import Path

PATTERNS = [
    ("Groq API key", re.compile(r"gsk_[A-Za-z0-9]{16,}")),
    ("OpenAI-style API key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("AWS key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("a secret assigned a value", re.compile(r"(?i)(?:api[_-]?key|secret|token|passwd|password)\s*[:=]\s*['\"][^'\"\s]{16,}['\"]")),
    ("email address", re.compile(r"[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com|example\.(?:com|org)|anthropic\.com)[A-Za-z0-9-]+\.[A-Za-z]{2,}")),
]
BAD_FILE_NAMES = re.compile(r"(^|/)(\.env(\.(?!example$)[^/]*)?|[^/]*\.(pem|key|wav|mp3|flac))$")
FAKE_MARKERS = ("FAKE", "secret-scan: fake")


def scan_filenames(names: list[str]) -> list[tuple[str, int, str]]:
    return [(n, 0, "a file that must never be committed (secrets, keys or audio)") for n in names if BAD_FILE_NAMES.search(n)]


def scan_added_lines(diff_text: str, private_words: list[str] | None = None) -> list[tuple[str, int, str]]:
    """Find problems in the lines a commit adds. Returns (file, line number, kind of problem)."""
    private = [w.lower() for w in (private_words or []) if w.strip()]
    findings: list[tuple[str, int, str]] = []
    current, line_no = "?", 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            current = raw[6:] if raw.startswith("+++ b/") else raw[4:]
            continue
        hunk = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", raw)
        if hunk:
            line_no = int(hunk.group(1)) - 1
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            line_no += 1
            text = raw[1:]
            if "secret-scan: fake" in text:
                continue
            for kind, pattern in PATTERNS:
                for match in pattern.finditer(text):
                    if any(marker.lower() in match.group(0).lower() for marker in FAKE_MARKERS):
                        continue
                    findings.append((current, line_no, kind))
            lowered = text.lower()
            for word in private:
                if word in lowered:
                    findings.append((current, line_no, "one of your private words (from .git/private-patterns.txt)"))
        elif not raw.startswith("-"):
            line_no += 1 if raw.startswith(" ") else 0
    return findings


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def main() -> int:
    names = _git("diff", "--cached", "--name-only", "--diff-filter=ACM").splitlines()
    git_dir = Path(_git("rev-parse", "--git-dir").strip() or ".git")
    words_file = git_dir / "private-patterns.txt"
    words = words_file.read_text(encoding="utf-8").splitlines() if words_file.is_file() else []
    findings = scan_filenames(names) + scan_added_lines(_git("diff", "--cached", "-U0", "--no-color"), words)
    if not findings:
        return 0
    print("COMMIT BLOCKED: this commit looks like it contains something private.\n", file=sys.stderr)
    for file, line, kind in findings:
        where = f"{file}:{line}" if line else file
        print(f"  {where}  ->  {kind}", file=sys.stderr)
    print(
        "\nNothing was committed. Remove the secret (and if it was a real key, delete that key at its provider and "
        "make a new one). If it is a harmless fake test value, add 'secret-scan: fake' on the same line.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
