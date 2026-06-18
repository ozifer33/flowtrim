from __future__ import annotations

import re


HOME_PREFIX = "/" + "Users" + "/"
WORK_PATH = "Documents" + "/" + "Work"
CODEX_DIR = "." + "codex"
ENV_FILE = "." + "env"
REL_PREFIX = r"(?:(?:\.\.?/)+)?"

PRIVATE_HOME_RE = re.compile(re.escape(HOME_PREFIX) + r"[^\s\"'<>]+")
WORK_PATH_RE = re.compile(
    r"(^|[\s\"'])" + REL_PREFIX + re.escape(WORK_PATH) + r"(/|[\s\"']|$)"
)
CODEX_PATH_RE = re.compile(
    r"(^|[\s\"'])(~?/|\$HOME/|" + REL_PREFIX + r")" + re.escape(CODEX_DIR) + r"/"
)
ENV_FILE_RE = re.compile(
    r"(^|[\s\"'])(read|open|load|source|cat)\s+"
    + REL_PREFIX
    + re.escape(ENV_FILE)
    + r"(/|[\s\"']|$)",
    re.IGNORECASE,
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"\b[A-Z0-9_]*(KEY|TOKEN|SECRET|PASSWORD)\b\s*[:=]\s*['\"]?"
    r"(sk-[A-Z0-9_-]+|[A-Z0-9][A-Z0-9_./+-]{11,})",
    re.IGNORECASE,
)


def scan_text(text: str) -> tuple[str, ...]:
    findings: list[str] = []
    if PRIVATE_HOME_RE.search(text):
        findings.append("private-path")
    if WORK_PATH_RE.search(text):
        findings.append("work-path")
    if CODEX_PATH_RE.search(text):
        findings.append("codex-path")
    if ENV_FILE_RE.search(text):
        findings.append("env-file")
    if SECRET_ASSIGNMENT_RE.search(text):
        findings.append("secret-like-env")
    return tuple(findings)
