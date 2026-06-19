from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .privacy import scan_text


SCHEMA = "flowtrim-install-check/v1"
PASS = "passed"
FAIL = "failed"
SKIP = "skipped-neutral"


def install_check_payload(
    root: str | Path = ".",
    *,
    tmp_root: str | Path = "/tmp/flowtrim-install-check",
    clean_clone_url: str | None = None,
    run_npx: bool = False,
    run_gh_skill: bool = False,
    run_claude_plugin: bool = False,
    tool_overrides: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root)
    scratch = _safe_scratch_root(repo_root, Path(tmp_root))
    tools = tool_overrides or {}
    checks = [
        _skill_source_shape(repo_root),
        _claude_plugin_metadata(repo_root),
        _node_project_install(repo_root, scratch, _tool("node", tools)),
        _shell_project_install(repo_root, scratch, _tool("node", tools)),
        _powershell_project_install(repo_root, scratch, _tool("pwsh", tools)),
        _clean_clone_install(clean_clone_url, scratch),
        _npx_github_install(run_npx, scratch, _tool("npx", tools)),
        _gh_skill_install(run_gh_skill, _tool("gh", tools)),
        _claude_plugin_install(run_claude_plugin, _tool("claude", tools)),
    ]
    payload = {
        "schema": SCHEMA,
        "valid": not any(check["status"] == FAIL for check in checks),
        "checks": checks,
        "privacy_findings": [],
    }
    text = json.dumps(payload, sort_keys=True)
    findings = list(scan_text(text))
    payload["privacy_findings"] = findings
    if findings:
        payload["valid"] = False
    return payload


def install_check_to_json(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, indent=2, sort_keys=True)
    _assert_safe(text)
    return text


def install_check_to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# FlowTrim Install Check",
        "",
        f"Valid: {payload['valid']}",
        "",
        "| Method | Status | Evidence | Files | Claim allowed |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for check in payload["checks"]:
        lines.append(
            "| {method} | {status} | {evidence} | {copied_file_count} | {claim_allowed} |".format(
                **check
            )
        )
    lines.extend(
        [
            "",
            f"Privacy findings: {len(payload.get('privacy_findings', []))}",
        ]
    )
    text = "\n".join(lines)
    _assert_safe(text)
    return text


def _skill_source_shape(root: Path) -> dict[str, Any]:
    skill = root / "skills" / "flowtrim"
    required = (
        skill / "SKILL.md",
        skill / "references" / "lane-policy.md",
        skill / "scripts" / "flowtrim_benchmark.py",
        skill / "agents" / "openai.yaml",
    )
    missing = [path.name for path in required if not path.exists()]
    if missing:
        return _check("skill-source-shape", FAIL, "skill allowlist incomplete")
    return _check("skill-source-shape", PASS, "skill allowlist present", len(required))


def _claude_plugin_metadata(root: Path) -> dict[str, Any]:
    marketplace = root / ".claude-plugin" / "marketplace.json"
    plugin = root / ".claude-plugin" / "plugin.json"
    if not marketplace.exists() or not plugin.exists():
        return _check("claude-plugin-metadata", FAIL, "plugin metadata missing")
    try:
        marketplace_data = json.loads(marketplace.read_text(encoding="utf-8"))
        plugin_data = json.loads(plugin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _check("claude-plugin-metadata", FAIL, "plugin metadata unreadable")
    if marketplace_data.get("name") != "flowtrim" or plugin_data.get("name") != "flowtrim":
        return _check("claude-plugin-metadata", FAIL, "plugin metadata name mismatch")
    if "./skills/flowtrim" not in plugin_data.get("skills", []):
        return _check("claude-plugin-metadata", FAIL, "plugin skill reference missing")
    return _check("claude-plugin-metadata", PASS, "plugin metadata shape valid", 2)


def _node_project_install(root: Path, scratch: Path, node: str | None) -> dict[str, Any]:
    if node is None:
        return _check("node-project-install", SKIP, "node unavailable")
    project = scratch / "node-project"
    result = _run(
        [
            node,
            "scripts/flowtrim-skill-install.mjs",
            "--agent",
            "codex",
            "--scope",
            "project",
            "--project",
            str(project),
            "--force",
        ],
        cwd=root,
    )
    if result.returncode != 0:
        return _check("node-project-install", FAIL, "node installer failed")
    return _installed_layout_check(project, ".agents/skills/flowtrim", "node-project-install")


def _shell_project_install(root: Path, scratch: Path, node: str | None) -> dict[str, Any]:
    if node is None:
        return _check("shell-project-install", SKIP, "node unavailable")
    project = scratch / "shell-project"
    result = _run(
        [
            "sh",
            "scripts/install-skill.sh",
            "--agent",
            "codex",
            "--scope",
            "project",
            "--project",
            str(project),
            "--force",
        ],
        cwd=root,
    )
    if result.returncode != 0:
        return _check("shell-project-install", FAIL, "shell installer failed")
    return _installed_layout_check(project, ".agents/skills/flowtrim", "shell-project-install")


def _powershell_project_install(root: Path, scratch: Path, pwsh: str | None) -> dict[str, Any]:
    if pwsh is None:
        return _check("powershell-project-install", SKIP, "pwsh unavailable")
    project = scratch / "powershell-project"
    result = _run(
        [
            pwsh,
            "-File",
            "scripts/install-skill.ps1",
            "--agent",
            "codex",
            "--scope",
            "project",
            "--project",
            str(project),
            "--force",
        ],
        cwd=root,
    )
    if result.returncode != 0:
        return _check("powershell-project-install", FAIL, "powershell installer failed")
    return _installed_layout_check(
        project,
        ".agents/skills/flowtrim",
        "powershell-project-install",
    )


def _clean_clone_install(clean_clone_url: str | None, scratch: Path) -> dict[str, Any]:
    if not clean_clone_url:
        return _check("clean-clone-install", SKIP, "clean clone not requested")
    clone = scratch / "clean-clone"
    if clone.exists():
        shutil.rmtree(clone)
    git = shutil.which("git")
    if git is None:
        return _check("clean-clone-install", SKIP, "git unavailable")
    clone_result = _run([git, "clone", "--depth", "1", clean_clone_url, str(clone)])
    if clone_result.returncode != 0:
        return _check("clean-clone-install", FAIL, "git clone failed")
    install = _run([sys.executable, "-m", "pip", "install", "."], cwd=clone)
    if install.returncode != 0:
        return _check("clean-clone-install", FAIL, "package install failed")
    smoke = _run([sys.executable, "-m", "flowtrim.cli.benchmark", "abcd"], cwd=clone)
    if smoke.returncode != 0 or smoke.stdout.strip() != "1":
        return _check("clean-clone-install", FAIL, "installed cli smoke failed")
    return _check("clean-clone-install", PASS, "clean clone cli smoke passed")


def _npx_github_install(run_npx: bool, scratch: Path, npx: str | None) -> dict[str, Any]:
    if not run_npx:
        return _check("npx-github-install", SKIP, "npx check not requested")
    if npx is None:
        return _check("npx-github-install", SKIP, "npx unavailable")
    project = scratch / "npx-project"
    result = _run(
        [
            npx,
            "github:ozifer33/flowtrim",
            "--agent",
            "codex",
            "--scope",
            "project",
            "--project",
            str(project),
            "--force",
        ]
    )
    if result.returncode != 0:
        return _check("npx-github-install", FAIL, "npx github install failed")
    return _installed_layout_check(project, ".agents/skills/flowtrim", "npx-github-install")


def _gh_skill_install(run_gh_skill: bool, gh: str | None) -> dict[str, Any]:
    if not run_gh_skill:
        return _check("gh-skill-install", SKIP, "gh skill check not requested")
    if gh is None:
        return _check("gh-skill-install", SKIP, "gh unavailable")
    preview = _run([gh, "skill", "preview", "ozifer33/flowtrim", "flowtrim"])
    if preview.returncode != 0:
        return _check("gh-skill-install", SKIP, "gh skill unavailable")
    return _check("gh-skill-install", PASS, "gh skill preview passed")


def _claude_plugin_install(run_claude_plugin: bool, claude: str | None) -> dict[str, Any]:
    if not run_claude_plugin:
        return _check("claude-plugin-install", SKIP, "claude plugin check not requested")
    if claude is None:
        return _check("claude-plugin-install", SKIP, "claude unavailable")
    return _check(
        "claude-plugin-install",
        SKIP,
        "manual Claude Code plugin install required",
    )


def _installed_layout_check(project: Path, rel: str, method: str) -> dict[str, Any]:
    target = project / rel
    required = (
        target / "SKILL.md",
        target / "references" / "lane-policy.md",
        target / "scripts" / "flowtrim_benchmark.py",
        target / "agents" / "openai.yaml",
    )
    if not all(path.exists() for path in required):
        return _check(method, FAIL, "installed skill layout incomplete")
    if (target / ".git").exists() or (target / ".env").exists():
        return _check(method, FAIL, "disallowed install artifact copied")
    return _check(method, PASS, "project install layout verified", _count_files(target))


def _check(
    method: str,
    status: str,
    evidence: str,
    copied_file_count: int = 0,
) -> dict[str, Any]:
    return {
        "method": method,
        "status": status,
        "evidence": evidence,
        "copied_file_count": copied_file_count,
        "skipped_reason": evidence if status == SKIP else None,
        "claim_allowed": _claim_allowed(method, status),
    }


def _claim_allowed(method: str, status: str) -> str:
    if status == PASS:
        return f"{method} passed local aggregate install check"
    if status == SKIP:
        return f"{method} has no install proof in this environment"
    return f"{method} blocked"


def _tool(name: str, overrides: dict[str, str | None]) -> str | None:
    if name in overrides:
        return overrides[name]
    return shutil.which(name)


def _safe_scratch_root(root: Path, requested: Path) -> Path:
    root_resolved = root.resolve()
    requested_resolved = requested.resolve()
    try:
        requested_resolved.relative_to(root_resolved)
    except ValueError:
        return requested
    return Path(tempfile.gettempdir()) / "flowtrim-install-check-run"


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = 120,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", "timeout")


def _count_files(root: Path) -> int:
    return sum(1 for path in root.rglob("*") if path.is_file())


def _assert_safe(text: str) -> None:
    if scan_text(text):
        raise ValueError("install-check privacy finding")
