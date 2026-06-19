import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flowtrim.benchmark import (
    build_work_commit_history_readonly_suite,
    report_to_json,
    run_suite,
)
from flowtrim.privacy import scan_text
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
    git(repo, "config", "user.email", "flowtrim@example.invalid")
    git(repo, "config", "user.name", "FlowTrim Test")
    return repo


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", ".")
    git(repo, "commit", "-m", message)


def write_code_file(path: Path, symbol: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    duplicate = f"  final repeated = normalizePrivateFixtureValue({symbol});"
    path.write_text(
        "\n".join(
            [
                f"void privateFixture{symbol}() {{",
                duplicate,
                duplicate,
                duplicate,
                "  return;",
                "}",
            ]
        ),
        encoding="utf-8",
    )


def create_history_repo(
    root: Path,
    name: str,
    extension: str,
    *,
    code_message: str = "private code-heavy commit message must not leak",
    control_message: str = "private generated control commit must not leak",
) -> Path:
    repo = init_repo(root, name)
    for index in range(1, 5):
        write_code_file(repo / "src" / f"private_feature_{index}.{extension}", str(index))
    write_code_file(repo / "lib" / "secret_keys" / f"private_secret.{extension}", "Secret")
    (repo / "assets" / "private-image.bin").parent.mkdir(parents=True, exist_ok=True)
    (repo / "assets" / "private-image.bin").write_bytes(b"\x00\x01\x02\x03")
    commit_all(repo, code_message)

    (repo / "pubspec.lock").write_text("\n".join(f"locked {i}" for i in range(120)))
    (repo / "ios" / "Generated.swiftinterface").parent.mkdir(parents=True, exist_ok=True)
    (repo / "ios" / "Generated.swiftinterface").write_text(
        "\n".join(f"generated {i}" for i in range(120)),
        encoding="utf-8",
    )
    commit_all(repo, control_message)
    return repo


class WorkCommitHistoryTest(unittest.TestCase):
    def test_work_commit_history_profile_uses_aliases_and_sanitized_buckets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dart_repo = create_history_repo(root, "private-ruejai-app", "dart")
            vue_repo = create_history_repo(root, "private-sc-frontend", "vue")

            report = run_suite(
                "work-commit-history-readonly",
                work_repos=[dart_repo, vue_repo],
                commit_limit=6,
                files_per_commit=2,
            )
            text = report_to_json(report)
            data = json.loads(text)

        case_ids = {case["case_id"] for case in data["cases"]}
        self.assertEqual(data["profile"], "work-commit-history-readonly")
        self.assertIn("work-history/repo-01/commit-001/code-01", case_ids)
        self.assertIn("work-history/repo-02/commit-001/code-01", case_ids)
        self.assertTrue(any("/command-" in case_id for case_id in case_ids))
        self.assertTrue(any("/exact-" in case_id for case_id in case_ids))
        self.assertTrue(any("/control-" in case_id for case_id in case_ids))
        self.assertGreaterEqual(data["metric_totals"]["code-lens"]["cases"], 2)
        self.assertGreaterEqual(data["metric_totals"]["token-bearing"]["wins"], 1)
        self.assertGreaterEqual(
            data["metric_totals"]["refusal-correctness"]["correct_refusals"],
            1,
        )
        self.assertTrue(data["runtime_changes"]["unapproved_filesystem_writes"] is False)
        self.assertNotIn(str(root), text)
        self.assertNotIn("private-ruejai-app", text)
        self.assertNotIn("private-sc-frontend", text)
        self.assertNotIn("private_feature", text)
        self.assertNotIn("private code-heavy commit message", text)
        self.assertNotIn("normalizePrivateFixtureValue", text)
        self.assertNotIn("secret_keys", text)
        self.assertEqual(scan_text(text), ())

    def test_work_commit_history_direct_builder_matches_profile_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = create_history_repo(Path(tmpdir), "private-ruejai-app", "dart")

            report = run_suite("work-commit-history-readonly", work_repos=[repo])
            direct_cases = build_work_commit_history_readonly_suite([repo])

        self.assertEqual(
            [case.case_id for case in report.cases],
            [case.case_id for case in direct_cases],
        )

    def test_preexisting_dirty_work_commit_history_repo_does_not_fail_runtime_gate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = create_history_repo(Path(tmpdir), "private-ruejai-app", "dart")
            (repo / "untracked-private-file.txt").write_text("dirty", encoding="utf-8")

            report = run_suite("work-commit-history-readonly", work_repos=[repo])
            text = report_to_json(report)
            data = json.loads(text)

        self.assertFalse(report.runtime_changes.unapproved_filesystem_writes)
        self.assertTrue(report.runtime_changes.preexisting_dirty_worktree)
        self.assertFalse(report.runtime_changes.post_status_changed)
        self.assertTrue(report.cases)
        self.assertGreaterEqual(report.metric_totals["token-bearing"]["wins"], 1)
        self.assertTrue(data["runtime_changes"]["preexisting_dirty_worktree"])
        self.assertFalse(data["runtime_changes"]["post_status_changed"])
        self.assertIn("pre_status_hash", data["runtime_changes"])
        self.assertIn("post_status_hash", data["runtime_changes"])
        self.assertNotIn("untracked-private-file", text)

    def test_post_run_status_change_still_blocks_work_commit_history_wins(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = create_history_repo(Path(tmpdir), "private-ruejai-app", "dart")

            with patch(
                "flowtrim.benchmark._run_readonly_git_status",
                side_effect=["", "?? generated-private-artifact.txt"],
            ):
                report = run_suite("work-commit-history-readonly", work_repos=[repo])

        self.assertTrue(report.runtime_changes.unapproved_filesystem_writes)
        self.assertTrue(report.runtime_changes.post_status_changed)
        self.assertTrue(report.cases)
        self.assertTrue(
            all(case.winner == "insufficient-evidence" for case in report.cases)
        )

    def test_private_commit_history_claim_boundaries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = create_history_repo(Path(tmpdir), "private-ruejai-app", "dart")
            report = run_suite("work-commit-history-readonly", work_repos=[repo])

        self.assertTrue(
            validate_claim(
                report,
                "FlowTrim has private local evidence from historical Work commits.",
            )
        )
        self.assertTrue(
            validate_claim(
                report,
                "Generated/lock-heavy commits are separated as controls.",
            )
        )
        self.assertFalse(validate_claim(report, "FlowTrim is a public benchmark."))
        self.assertFalse(validate_claim(report, "FlowTrim is a global benchmark."))

    def test_work_dogfood_profile_uses_group_aliases_without_leaking_selectors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = create_history_repo(
                root,
                "private-ruejai-backend-admin",
                "ts",
                code_message="RJ-735 private code-heavy commit message must not leak",
            )

            report = run_suite(
                "work-dogfood-readonly",
                work_repos=[repo],
                work_groups=["RJ-735"],
                commit_limit=4,
                files_per_commit=1,
            )
            text = report_to_json(report)
            data = json.loads(text)

        case_ids = {case["case_id"] for case in data["cases"]}
        self.assertEqual(data["profile"], "work-dogfood-readonly")
        self.assertIn("work-dogfood/repo-01/group-01/commit-001/code-01", case_ids)
        self.assertGreaterEqual(data["metric_totals"]["token-bearing"]["wins"], 1)
        self.assertGreaterEqual(
            data["metric_totals"]["refusal-correctness"]["correct_refusals"],
            1,
        )
        self.assertNotIn(str(root), text)
        self.assertNotIn("private-ruejai-backend-admin", text)
        self.assertNotIn("private code-heavy commit message", text)
        self.assertNotIn("RJ-735", text)
        self.assertNotIn("private_feature", text)
        self.assertNotIn("normalizePrivateFixtureValue", text)
        self.assertEqual(scan_text(text), ())


if __name__ == "__main__":
    unittest.main()
