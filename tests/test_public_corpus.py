import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from flowtrim.benchmark import report_to_json, run_suite
from flowtrim.privacy import scan_text
from flowtrim.public_corpus import (
    load_public_corpus_manifest,
    prepare_public_corpus,
)
from flowtrim.publication import validate_claim


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def init_repo(root: Path, name: str) -> Path:
    repo = root / name
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "flowtrim-public@example.invalid")
    git(repo, "config", "user.name", "FlowTrim Public Test")
    return repo


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD").strip()


def write_code_file(path: Path, symbol: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    repeated = f"  const repeated = normalizePublicFixtureValue({symbol});"
    path.write_text(
        "\n".join(
            [
                f"export function publicFixture{symbol}(input: string) {{",
                repeated,
                repeated,
                repeated,
                "  return input;",
                "}",
            ]
        ),
        encoding="utf-8",
    )


def create_public_history_repo(root: Path) -> tuple[Path, str]:
    repo = init_repo(root, "public-source")
    for index in range(1, 5):
        write_code_file(repo / "src" / f"public_feature_{index}.ts", str(index))
    commit_all(repo, "public code-heavy message must not leak")

    (repo / "package-lock.json").write_text(
        "\n".join(f"locked public dependency {index}" for index in range(80)),
        encoding="utf-8",
    )
    (repo / "generated" / "bundle.g.dart").parent.mkdir(exist_ok=True)
    (repo / "generated" / "bundle.g.dart").write_text(
        "\n".join(f"generated public artifact {index}" for index in range(80)),
        encoding="utf-8",
    )
    pinned = commit_all(repo, "public control message must not leak")
    return repo, pinned


def write_manifest(path: Path, *, pinned_commit: str) -> Path:
    data = {
        "schema": "flowtrim-public-corpus/v1",
        "repos": [
            {
                "url": "https://github.com/example/public-source.git",
                "branch": "main",
                "pinned_commit": pinned_commit,
                "license": "MIT",
                "language_family": "typescript",
                "fetch_depth": 20,
                "include_extensions": [".ts", ".tsx", ".js", ".jsx", ".vue", ".dart"],
                "exclude_extensions": [".lock", ".json", ".g.dart"],
            }
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class PublicCorpusTest(unittest.TestCase):
    def test_manifest_rejects_unsafe_or_unpinned_entries(self):
        cases = [
            (
                {"url": "https://github.com/example/repo.git", "branch": "main"},
                "license",
            ),
            (
                {
                    "url": "https://github.com/example/repo.git",
                    "branch": "main",
                    "license": "MIT",
                    "pinned_commit": "main",
                },
                "pinned_commit",
            ),
            (
                {
                    "url": "git@github.com:example/repo.git",
                    "branch": "main",
                    "license": "MIT",
                    "pinned_commit": "a" * 40,
                },
                "public https",
            ),
            (
                {
                    "url": "/tmp/private/repo",
                    "branch": "main",
                    "license": "MIT",
                    "pinned_commit": "a" * 40,
                },
                "public https",
            ),
            (
                {
                    "url": "https://github.com/example/repo.git",
                    "branch": "main",
                    "license": "MIT",
                    "pinned_commit": "a" * 40,
                    "raw_source": "export const secret = true",
                },
                "unsupported manifest key",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            for entry, message in cases:
                with self.subTest(message=message):
                    path = Path(tmpdir) / "manifest.json"
                    path.write_text(
                        json.dumps({"schema": "flowtrim-public-corpus/v1", "repos": [entry]}),
                        encoding="utf-8",
                    )

                    with self.assertRaisesRegex(ValueError, message):
                        load_public_corpus_manifest(path)

    def test_prepare_public_corpus_uses_cache_root_without_source_paths_in_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = write_manifest(Path(tmpdir) / "manifest.json", pinned_commit="a" * 40)
            cache_root = Path(tmpdir) / "cache"
            commands = []

            def runner(args, cwd=None):
                commands.append((tuple(args), cwd))
                return ""

            result = prepare_public_corpus(manifest, cache_root, runner=runner)

        self.assertEqual(result["prepared"], 1)
        self.assertEqual(result["repos"][0]["alias"], "repo-01")
        self.assertNotIn("public-source", json.dumps(result))
        self.assertTrue(commands)
        self.assertTrue(all(Path(cwd) == cache_root for _, cwd in commands if cwd is not None))

    def test_public_corpus_profile_fails_clearly_when_cache_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = write_manifest(Path(tmpdir) / "manifest.json", pinned_commit="a" * 40)

            with self.assertRaisesRegex(ValueError, "public corpus cache missing: repo-01"):
                run_suite(
                    "public-open-source-readonly",
                    public_corpus_manifest=manifest,
                    public_cache_root=Path(tmpdir) / "missing-cache",
                )

    def test_public_corpus_profile_uses_aliases_and_case_families(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_repo, pinned = create_public_history_repo(root)
            cache_root = root / "cache"
            cache_root.mkdir()
            subprocess.run(
                ["git", "clone", str(source_repo), str(cache_root / "repo-01")],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = write_manifest(root / "manifest.json", pinned_commit=pinned)

            report = run_suite(
                "public-open-source-readonly",
                public_corpus_manifest=manifest,
                public_cache_root=cache_root,
                commit_limit=4,
                files_per_commit=2,
            )
            text = report_to_json(report)
            data = json.loads(text)

        case_ids = {case["case_id"] for case in data["cases"]}
        self.assertEqual(data["profile"], "public-open-source-readonly")
        self.assertTrue(any("/command-" in case_id for case_id in case_ids))
        self.assertTrue(any("/exact-" in case_id for case_id in case_ids))
        self.assertTrue(any("/code-" in case_id for case_id in case_ids))
        self.assertTrue(any("/control-" in case_id for case_id in case_ids))
        self.assertGreaterEqual(data["metric_totals"]["token-bearing"]["cases"], 1)
        self.assertGreaterEqual(data["metric_totals"]["refusal-correctness"]["correct_refusals"], 1)
        self.assertGreaterEqual(data["metric_totals"]["code-lens"]["cases"], 1)
        self.assertFalse(data["runtime_changes"]["unapproved_filesystem_writes"])
        self.assertNotIn(str(root), text)
        self.assertNotIn("public-source", text)
        self.assertNotIn("public_feature", text)
        self.assertNotIn("normalizePublicFixtureValue", text)
        self.assertNotIn("public code-heavy message", text)
        self.assertEqual(scan_text(text), ())

    def test_public_corpus_claim_boundaries_are_pinned_not_global(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_repo, pinned = create_public_history_repo(root)
            cache_root = root / "cache"
            cache_root.mkdir()
            subprocess.run(
                ["git", "clone", str(source_repo), str(cache_root / "repo-01")],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = write_manifest(root / "manifest.json", pinned_commit=pinned)
            report = run_suite(
                "public-open-source-readonly",
                public_corpus_manifest=manifest,
                public_cache_root=cache_root,
                commit_limit=4,
                files_per_commit=1,
            )

        self.assertTrue(
            validate_claim(
                report,
                "On the pinned public corpus, FlowTrim selected a safe lower-token method for measured lanes.",
            )
        )
        self.assertTrue(
            validate_claim(
                report,
                "Generated/lock-heavy public commits are separated as controls.",
            )
        )
        self.assertFalse(
            validate_claim(report, "FlowTrim globally beats RTK, Ponytail, and Headroom.")
        )


if __name__ == "__main__":
    unittest.main()
