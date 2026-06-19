from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .privacy import scan_text


DOCS_CHECK_SCHEMA = "flowtrim-docs-check/v1"
REQUIRED_PUBLIC_DOCS = (
    "README.md",
    "QUICKSTART.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "docs/install.md",
    "docs/install-verification.md",
    "docs/benchmark-results.md",
    "docs/assets/flowtrim-public-alpha-benchmark.svg",
    "benchmarks/results/2026-06-19-public-alpha.md",
    "skills/flowtrim/SKILL.md",
)
SOURCE_FALLBACK_HEADING = "source-checkout fallback"
SOURCE_FALLBACK_INLINE = "source checkout fallback"


def docs_check_payload(root: str | Path = ".") -> dict[str, Any]:
    repo_root = Path(root)
    findings: list[dict[str, str]] = []
    for rel in REQUIRED_PUBLIC_DOCS:
        path = repo_root / rel
        if not path.exists():
            findings.append({"target": "docs", "finding": f"missing required doc: {rel}"})
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            findings.append({"target": "docs", "finding": f"unreadable doc: {rel}"})
            continue
        findings.extend(_command_findings(rel, text))
        findings.extend(_privacy_findings(rel, text))

    return {
        "schema": DOCS_CHECK_SCHEMA,
        "valid": not findings,
        "findings": findings,
    }


def docs_check_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def docs_check_to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# FlowTrim Docs Check",
        "",
        f"Valid: {payload['valid']}",
        f"Findings: {len(payload['findings'])}",
    ]
    lines.extend(f"- {item['target']}: {item['finding']}" for item in payload["findings"])
    return "\n".join(lines)


def _command_findings(rel: str, text: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    current_heading = ""
    for line in text.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("#"):
            current_heading = stripped
        fallback_allowed = (
            SOURCE_FALLBACK_HEADING in current_heading
            or SOURCE_FALLBACK_HEADING in stripped
            or SOURCE_FALLBACK_INLINE in stripped
        )
        if "pythonpath=src" in stripped and not fallback_allowed:
            findings.append(
                {
                    "target": "docs",
                    "finding": f"{rel} uses source-checkout command outside fallback section",
                }
            )
        if "skills/flowtrim/scripts/" in stripped and not fallback_allowed:
            findings.append(
                {
                    "target": "docs",
                    "finding": f"{rel} uses skill script path outside fallback section",
                }
            )
    return findings


def _privacy_findings(rel: str, text: str) -> list[dict[str, str]]:
    return [
        {"target": "docs", "finding": f"{rel} privacy finding: {finding}"}
        for finding in scan_text(text)
    ]
