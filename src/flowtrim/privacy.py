from __future__ import annotations

import re


PRIVATE_PATH_RE = re.compile(r"/Users/[^\s]+/(Documents/Work|\.codex|Library)")
SECRET_ENV_RE = re.compile(r"[A-Z0-9_]*(KEY|TOKEN|SECRET|PASSWORD)=[^\s]+")


def scan_text(text: str) -> tuple[str, ...]:
    findings: list[str] = []
    if PRIVATE_PATH_RE.search(text):
        findings.append("private-path")
    if SECRET_ENV_RE.search(text):
        findings.append("secret-like-env")
    return tuple(findings)
