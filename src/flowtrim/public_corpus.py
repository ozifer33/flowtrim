from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


PUBLIC_CORPUS_SCHEMA = "flowtrim-public-corpus/v1"
PUBLIC_CORPUS_AUDIT_SCHEMA = "flowtrim-public-corpus-audit/v1"
PUBLIC_OPEN_SOURCE_PROFILE = "public-open-source-readonly"
DEFAULT_PUBLIC_CORPUS_MANIFEST = (
    Path(__file__).resolve().parents[2] / "benchmarks" / "public-corpus" / "manifest.v1.json"
)
DEFAULT_PUBLIC_CACHE_ROOT = Path("/tmp/flowtrim-public-corpus")
PINNED_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_REPO_KEYS = frozenset(
    {
        "url",
        "branch",
        "pinned_commit",
        "license",
        "language_family",
        "fetch_depth",
        "include_extensions",
        "exclude_extensions",
    }
)


@dataclass(frozen=True)
class PublicRepoSpec:
    alias: str
    url: str
    branch: str
    pinned_commit: str
    license: str
    language_family: str
    fetch_depth: int
    include_extensions: tuple[str, ...]
    exclude_extensions: tuple[str, ...]


@dataclass(frozen=True)
class PublicCorpusManifest:
    repos: tuple[PublicRepoSpec, ...]


Runner = Callable[[list[str], Path | None], str]


def load_public_corpus_manifest(path: str | Path) -> PublicCorpusManifest:
    manifest_path = Path(path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("schema") != PUBLIC_CORPUS_SCHEMA:
        raise ValueError("public corpus manifest schema must be flowtrim-public-corpus/v1")

    repos_data = data.get("repos")
    if not isinstance(repos_data, list) or not repos_data:
        raise ValueError("public corpus manifest requires repos")

    repos = []
    for index, entry in enumerate(repos_data, start=1):
        repos.append(_repo_spec_from_entry(index, entry))
    return PublicCorpusManifest(repos=tuple(repos))


def audit_public_corpus_manifest(path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _audit_payload([], [{"target": "manifest", "finding": "manifest unreadable"}])

    findings: list[dict[str, str]] = []
    if data.get("schema") != PUBLIC_CORPUS_SCHEMA:
        findings.append({"target": "manifest", "finding": "schema mismatch"})

    repos_data = data.get("repos")
    if not isinstance(repos_data, list) or not repos_data:
        findings.append({"target": "manifest", "finding": "repos missing"})
        repos_data = []

    specs: list[PublicRepoSpec] = []
    for index, entry in enumerate(repos_data, start=1):
        target = f"repo-{index:03d}"
        try:
            specs.append(_repo_spec_from_entry(index, entry))
        except ValueError as exc:
            findings.append({"target": target, "finding": str(exc)})

    return _audit_payload(specs, findings)


def prepare_public_corpus(
    manifest_path: str | Path,
    cache_root: str | Path,
    *,
    runner: Runner | None = None,
    source_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    manifest = load_public_corpus_manifest(manifest_path)
    root = Path(cache_root)
    root.mkdir(parents=True, exist_ok=True)
    run = runner or _run_prepare_command
    overrides = source_overrides or {}

    repos = []
    for spec in manifest.repos:
        source = overrides.get(spec.alias, spec.url)
        target = root / spec.alias
        if target.exists():
            run(
                [
                    "git",
                    "-C",
                    spec.alias,
                    "fetch",
                    "--no-tags",
                    "--depth",
                    str(spec.fetch_depth),
                    "origin",
                    spec.pinned_commit,
                ],
                root,
            )
        else:
            run(
                [
                    "git",
                    "clone",
                    "--no-tags",
                    "--depth",
                    str(spec.fetch_depth),
                    source,
                    spec.alias,
                ],
                root,
            )
            run(
                [
                    "git",
                    "-C",
                    spec.alias,
                    "fetch",
                    "--no-tags",
                    "--depth",
                    str(spec.fetch_depth),
                    "origin",
                    spec.pinned_commit,
                ],
                root,
            )
        run(["git", "-C", spec.alias, "checkout", "--detach", spec.pinned_commit], root)
        run(["git", "-C", spec.alias, "cat-file", "-e", f"{spec.pinned_commit}^{{commit}}"], root)
        repos.append(
            {
                "alias": spec.alias,
                "pinned_commit": spec.pinned_commit[:12],
                "license": spec.license,
                "language_family": spec.language_family,
            }
        )

    return {"schema": PUBLIC_CORPUS_SCHEMA, "prepared": len(repos), "repos": repos}


def _audit_payload(
    specs: list[PublicRepoSpec],
    findings: list[dict[str, str]],
) -> dict[str, Any]:
    language_families = sorted({spec.language_family for spec in specs})
    licenses = sorted({spec.license for spec in specs})
    return {
        "schema": PUBLIC_CORPUS_AUDIT_SCHEMA,
        "valid": not findings,
        "repo_count": len(specs),
        "language_families": language_families,
        "licenses": licenses,
        "case_family_coverage": [
            "public-command-output",
            "public-code-lens",
            "public-exact-evidence",
            "public-control",
        ]
        if specs
        else [],
        "findings": findings,
    }


def public_repo_cache_path(cache_root: str | Path, spec: PublicRepoSpec) -> Path:
    return Path(cache_root) / spec.alias


def _repo_spec_from_entry(index: int, entry: Any) -> PublicRepoSpec:
    if not isinstance(entry, dict):
        raise ValueError("public corpus repo entry must be an object")
    extra_keys = set(entry) - ALLOWED_REPO_KEYS
    if extra_keys:
        raise ValueError("unsupported manifest key: " + sorted(extra_keys)[0])

    required = ("url", "branch", "license")
    for key in required:
        if not entry.get(key):
            raise ValueError(f"public corpus repo requires {key}")

    url = str(entry["url"])
    if not (url.startswith("https://github.com/") and not url.endswith("/")):
        raise ValueError("public corpus url must be public https GitHub URL")

    if not entry.get("pinned_commit"):
        raise ValueError("public corpus repo requires pinned_commit")
    pinned_commit = str(entry["pinned_commit"])
    if not PINNED_COMMIT_RE.fullmatch(pinned_commit):
        raise ValueError("public corpus pinned_commit must be a 40-char hex SHA")

    if not entry.get("language_family"):
        raise ValueError("public corpus repo requires language_family")

    fetch_depth = int(entry.get("fetch_depth", 50))
    if fetch_depth < 1:
        raise ValueError("public corpus fetch_depth must be positive")

    return PublicRepoSpec(
        alias=f"repo-{index:02d}",
        url=url,
        branch=str(entry["branch"]),
        pinned_commit=pinned_commit,
        license=str(entry["license"]),
        language_family=str(entry["language_family"]),
        fetch_depth=fetch_depth,
        include_extensions=tuple(entry.get("include_extensions", ())),
        exclude_extensions=tuple(entry.get("exclude_extensions", ())),
    )


def _run_prepare_command(args: list[str], cwd: Path | None) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError("public corpus prepare command failed")
    return result.stdout
