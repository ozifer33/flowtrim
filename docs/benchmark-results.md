# FlowTrim Benchmark Results

This document explains what the FlowTrim proof suite tests, what passed in the
latest local run, and which claims the results do and do not support. It is
written for a future public repo: private Work evidence is described only as
anonymous aggregate data, with no repo names, local paths, commit messages, file
paths, source lines, or raw diffs.

## Latest Proof Run

Local run date: June 18, 2026.

Report schema: `flowtrim-benchmark/v1`.

Runtime posture: read-only and non-invasive. Every report in this run recorded
`false` for installs, hooks, proxy, MCP registration, config writes, telemetry,
raw-output storage, and unapproved filesystem writes.

Tool posture:

- `rtk` was available in the local run.
- `headroom` was not installed, so Headroom cases are neutral skipped coverage,
  not a Headroom loss.

## Result Summary

| Profile | Corpus type | Cases | Main result | Claim status |
| --- | --- | ---: | --- | --- |
| `synthetic-heavy` | Public-safe synthetic fixtures | 14 | 4 measured token-bearing wins, 528 estimated tokens saved, 3 correct raw refusals, 2 code-lens wins | Publishable as fixture evidence |
| `aql-vault-readonly` | Read-only vault decision fixtures | 6 | Vault verdict stayed `hybrid-only`; 4 semantic cases deferred to Atlas context economy | Supports keeping Atlas as vault baseline |
| `work-code-readonly` | Private local anonymous code sample | 84 | 84 code-lens wins, 0 token-bearing claims | Private local evidence only |
| `work-commit-history-readonly` | Private local anonymous commit history | 49 | 10 token-bearing wins, 36,649 estimated tokens saved, 10 correct raw refusals, 27 code-lens wins | Private local evidence only |

These totals are lane-specific. A win in one lane does not imply FlowTrim should
replace raw output, Atlas context economy, RTK, Ponytail, or Headroom globally.

## What Was Tested

### Synthetic Heavy

The `synthetic-heavy` profile is the public-safe proof corpus. It contains
fixtures designed to exercise the boundaries where token reduction is useful and
where it must refuse.

Native command-output comparison is the first implementation stage of the final
direction. The noisy command fixtures compare raw, RTK fixture replay, and
`flowtrim-native-command`; wins count only when required facts survive and the
native packet is smaller within budget.

Command-output cases tested:

- `command-output/short-empty`: raw output must win, because a short or empty
  command has no meaningful compression opportunity.
- `command-output/noisy-build-pass`: RTK or FlowTrim selection may win only when
  required path, feature flag, and pass summary remain preserved.
- `command-output/noisy-build-fail`: compact output may win only when file path,
  error label, and failing test id remain preserved.
- `mutation/missing-path`: must become `insufficient-evidence` when a required
  path is lost.
- `mutation/slower-candidate`: raw must win when the compact candidate exceeds
  the wall-time budget.
- `mutation/guard-failure`: must become `insufficient-evidence` when guard
  metrics fail.

Long-context cases tested:

- `long-context/tool-trace`: compact output may win only when trace id, job id,
  source id, and failure facts remain auditable.
- `long-context/handoff`: compact output may win only when requirement id,
  no-install constraint, test path, and source path remain preserved.
- `long-context/marker-only-unsafe`: marker-only context must be
  `insufficient-evidence` without a retrieval path.
- `headroom-direct`: skipped is neutral when the tool is unavailable. If the tool
  is installed later, only direct read-only compression should be tested.

Exact-evidence cases tested:

- `exact-evidence/source-quote`
- `exact-evidence/failing-stack-trace`
- `exact-evidence/line-level-diff`

All exact-evidence cases selected raw with correct refusal behavior. Smaller
summaries do not count as wins for exact quotes, diffs, stack traces, security
evidence, failing validation, or explicit exact-output requests.

Code-lens cases tested:

- `code/over-abstract-helper.txt`
- `code/duplicate-conversion-logic.txt`

These cases validate Ponytail-style complexity pressure. The evidence is a
delete-list and reduced generated complexity without requirement or test-surface
loss. It is not a direct token-saving claim.

Synthetic totals:

- `token-bearing`: 9 cases, 4 wins, 528 estimated tokens saved, 3
  `insufficient-evidence`, 2 skipped methods.
- `refusal-correctness`: 3 cases, 3 correct refusals.
- `code-lens`: 2 cases, 2 wins, 6 delete items, 3 duplicate abstractions, 6
  generated LOC removed.
- `vault-semantic`: 0 cases.

### Aql Vault Read-Only

The `aql-vault-readonly` profile tests whether FlowTrim should replace the vault
context economy. Current result: it should not.

Cases tested:

- `vault/short-command`: raw won.
- `vault/rtk-candidate`: raw won because the measured candidate did not safely
  beat raw.
- `vault/packet-routing`: deferred to Atlas context economy.
- `vault/index-inventory`: deferred to Atlas context economy.
- `vault/source-id-preservation`: deferred to Atlas context economy.
- `vault/approval-boundary`: deferred to Atlas context economy.

Vault totals:

- `token-bearing`: 2 cases, 0 wins, 0 estimated tokens saved.
- `vault-semantic`: 4 cases, 4 Atlas deferrals.
- Final verdict: `hybrid-only`.

Interpretation: Atlas remains the default semantic system for vault work. FlowTrim
can still help in narrow command-output or long-context lanes, but the vault
should keep Atlas packet routing, `llm_brief`, source summaries, generated
indexes, and approval boundaries as its baseline context economy.

### Work Code Read-Only

The `work-code-readonly` profile is private local evidence. It is intentionally
anonymous and aggregate-only.

What it tests:

- A high-signal sample of code files across private repositories.
- Whether Ponytail-style code-lens analysis can identify removable helper
  abstractions, duplicate conversion logic, or generated complexity.
- Whether the report can stay anonymous: repo labels, file labels, hashes, and
  aggregate metrics only.

Totals from the latest local run:

- `code-lens`: 84 cases, 84 wins.
- Delete-list items: 305.
- Duplicate abstractions: 233.
- Generated LOC delta: -2,429.
- `token-bearing`: 0 cases and 0 claims.

Interpretation: this supports the private claim that FlowTrim can identify
code-complexity reduction opportunities in Work code without changing repos. It
does not support a public benchmark claim and does not prove Ponytail saved
tokens, because no generated-token measurement is counted in this profile.

### Work Commit-History Read-Only

The `work-commit-history-readonly` profile is private local evidence from
historical commits. It reads commit metadata, stat/numstat output, and selected
post-commit code blobs through read-only git commands. It does not check out old
commits, write to the worktree, store commit messages, store file paths, or store
raw source/diff content.

What it tests:

- Code-heavy commits: useful for code-lens cases.
- Command-output-heavy commit stats: useful for raw-vs-RTK comparison.
- Generated, vendor, lock, native, or config churn: separated as control cases.
- Exact-evidence cases: raw must win when line-level or diff-sensitive evidence
  is required.

Totals from the latest local run:

- `token-bearing`: 12 cases, 10 wins, 36,649 estimated tokens saved.
- `refusal-correctness`: 10 cases, 10 correct refusals.
- `code-lens`: 27 cases, 27 wins.
- Delete-list items: 95.
- Duplicate abstractions: 78.
- Generated LOC delta: -738.

Interpretation: this supports the private local claim that FlowTrim can find
command-output and code-lens opportunities in historical Work commits without
changing repositories, while separating generated/lock-heavy commits as controls.
It does not support public or global benchmark claims.

## Acceptance Gates

Token-bearing wins count only when all of these are true:

- The candidate uses fewer estimated tokens than raw output.
- Required facts are preserved.
- Preservation checks pass with no missing must-keep items.
- Wall-time stays within the benchmark budget.
- Runtime changes stay false.
- The lane allows summarization or compaction.

Raw output must be selected when:

- The output is already short or empty.
- The request asks for exact evidence.
- The evidence is a quote, stack trace, line-level diff, security evidence,
  failing validation output, or explicit exact-output request.
- A compact candidate loses required facts.
- A compact candidate is slower than the wall-time budget.

Code-lens wins count only when:

- The delete-list reduces generated complexity.
- Requirement surface is unaffected.
- Test surface is unaffected.
- Must-keep rules are preserved.
- The result is reported as complexity evidence, not token compression.

Vault semantic wins are intentionally conservative:

- Atlas context economy remains the baseline for vault routing, source identity,
  summaries, indexes, and approval boundaries.
- The vault verdict remains `hybrid-only` unless every required vault family
  passes, runtime is unchanged, and there is a real measured vault token win.

Privacy and non-invasive gates:

- Reports must contain no private home paths, Work paths, repo names, file names,
  raw source lines, raw diffs, secret-like values, hidden skill paths, or raw
  private output.
- Report writes must stay out of private Work roots.
- Report write acknowledgements print only the report basename.
- Runtime changes must stay false for installs, hooks, proxy, MCP, config
  writes, telemetry, raw-output storage, and unapproved filesystem writes.

## Reproduction Commands

Unit and invariant tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Skill validation:

```bash
uv run --no-project --with PyYAML python <SKILL_CREATOR_QUICK_VALIDATE> skills/flowtrim
```

Public-safe synthetic proof:

```bash
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile synthetic-heavy --format json
```

Vault proof with a local vault path:

```bash
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile aql-vault-readonly --format json --aql-root <AQL_ATLAS_ROOT>
```

Private Work code-lens proof:

```bash
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile work-code-readonly --format json --work-root <WORK_ROOT> --repo-limit 9 --files-per-repo 12
```

Private Work commit-history proof:

```bash
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile work-commit-history-readonly --format json --work-repo <WORK_REPO_A> --work-repo <WORK_REPO_B>
```

Privacy scan over tracked and untracked public repo files:

```bash
PYTHONPATH=src python3 - <<'PY'
from pathlib import Path
import subprocess
from flowtrim.privacy import scan_text

root = Path.cwd()
paths = subprocess.run(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
    cwd=root,
    check=True,
    capture_output=True,
    text=True,
).stdout.splitlines()

bad = []
for rel in paths:
    path = root / rel
    if path.is_file() and "benchmarks/reports/" not in rel:
        findings = scan_text(path.read_text(errors="ignore"))
        if findings:
            bad.append((rel, findings))

print(bad)
raise SystemExit(1 if bad else 0)
PY
```

Expected result: `[]`.

## Claim Boundaries

Allowed:

- FlowTrim selected a safe lower-token method for measured command-output or
  long-context lanes.
- FlowTrim correctly selected raw for unsafe exact-evidence lanes.
- Ponytail-style code lens reduced generated code complexity in measured cases.
- Atlas context economy remains the recommended vault baseline in the current
  proof.
- FlowTrim has private local evidence from anonymous historical Work commits.
- Generated/lock-heavy commits are separated as controls.

Forbidden:

- FlowTrim is a public benchmark based on private Work evidence.
- FlowTrim is a global benchmark.
- FlowTrim globally beats RTK, Ponytail, or Headroom.
- Headroom lost when it was skipped because unavailable.
- Ponytail saved tokens without generated-token measurement.
- The vault is FlowTrim-safe while the verdict remains `hybrid-only`.
- Any claim that names private repos, exposes commit messages, quotes source, or
  quotes diff content.

## Public Release Gap

The remaining gap for public/global comparison is a separate
`public-open-source-readonly` corpus. That corpus should use only public repos,
public commits, and publishable reports. Until then, FlowTrim can publish
synthetic fixture evidence and describe private Work runs only as local,
anonymous, aggregate evidence.
