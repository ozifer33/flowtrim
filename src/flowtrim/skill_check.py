from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .privacy import scan_text


SKILL_CHECK_SCHEMA = "flowtrim-skill-check/v1"
REQUIRED_HEADINGS = ("# FlowTrim", "## Route", "## Commands", "## Do Not Use When")
SCRIPT_REF_RE = re.compile(r"skills/flowtrim/scripts/[A-Za-z0-9_.-]+\.py")


def skill_check_payload(skill_root: str | Path) -> dict[str, Any]:
    root = Path(skill_root)
    skill_path = root / "SKILL.md"
    findings: list[dict[str, str]] = []
    try:
        text = skill_path.read_text(encoding="utf-8")
    except OSError:
        return _payload([{"target": "skill-root", "finding": "missing SKILL.md"}])

    findings.extend(_frontmatter_findings(text))
    findings.extend(_heading_findings(text))
    findings.extend(_script_reference_findings(root, text))
    findings.extend(_privacy_findings(root))
    return _payload(findings)


def skill_check_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def skill_check_to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# FlowTrim Skill Check",
        "",
        f"Valid: {payload['valid']}",
        f"Findings: {len(payload['findings'])}",
    ]
    lines.extend(f"- {finding['target']}: {finding['finding']}" for finding in payload["findings"])
    return "\n".join(lines)


def _payload(findings: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema": SKILL_CHECK_SCHEMA,
        "valid": not findings,
        "findings": findings,
    }


def _frontmatter_findings(text: str) -> list[dict[str, str]]:
    block = _frontmatter_block(text)
    findings = []
    if block is None:
        return [{"target": "skill-root", "finding": "missing frontmatter"}]
    if not _has_frontmatter_field(block, "name"):
        findings.append({"target": "skill-root", "finding": "missing frontmatter name"})
    if not _has_frontmatter_field(block, "description"):
        findings.append({"target": "skill-root", "finding": "missing frontmatter description"})
    return findings


def _frontmatter_block(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    marker = "\n---"
    end = text.find(marker, 4)
    if end == -1:
        return None
    return text[4:end]


def _has_frontmatter_field(block: str, name: str) -> bool:
    prefix = f"{name}:"
    return any(line.startswith(prefix) and line[len(prefix) :].strip() for line in block.splitlines())


def _heading_findings(text: str) -> list[dict[str, str]]:
    return [
        {"target": "skill-root", "finding": f"missing heading: {heading}"}
        for heading in REQUIRED_HEADINGS
        if heading not in text
    ]


def _script_reference_findings(skill_root: Path, text: str) -> list[dict[str, str]]:
    repo_root = _repo_root_for_skill(skill_root)
    findings = []
    for index, ref in enumerate(sorted(set(SCRIPT_REF_RE.findall(text))), start=1):
        if not (repo_root / ref).exists():
            findings.append(
                {
                    "target": f"script-ref-{index:03d}",
                    "finding": "referenced command script is missing",
                }
            )
    return findings


def _repo_root_for_skill(skill_root: Path) -> Path:
    resolved = skill_root.resolve()
    if resolved.name == "flowtrim" and resolved.parent.name == "skills":
        return resolved.parents[1]
    return resolved


def _privacy_findings(skill_root: Path) -> list[dict[str, str]]:
    docs = [skill_root / "SKILL.md"]
    references = skill_root / "references"
    if references.exists():
        docs.extend(sorted(references.rglob("*.md")))

    findings = []
    for index, path in enumerate(docs, start=1):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for finding in scan_text(text):
            findings.append(
                {
                    "target": f"skill-doc-{index:03d}",
                    "finding": f"privacy finding: {finding}",
                }
            )
    return findings
