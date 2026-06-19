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
| `public-playground-readonly` | Public-safe onboarding scenarios | 12 | 8 measured token-bearing wins, 2,826 estimated tokens saved, 2 correct raw refusals, 1 code-lens win | Publishable as usability smoke evidence |
| `public-open-source-readonly` | Pinned public open-source commits | 114 | 22 measured token-bearing wins, 2,412 estimated tokens saved, 22 correct raw refusals, 62 code-lens wins | Publishable only as pinned-corpus evidence |
| `aql-vault-readonly` | Read-only vault decision fixtures | 6 | Vault verdict stayed `hybrid-only`; 4 semantic cases deferred to Atlas context economy | Supports keeping Atlas as vault baseline |
| `work-code-readonly` | Private local anonymous code sample | 84 | 84 code-lens wins, 0 token-bearing claims | Private local evidence only |
| `work-commit-history-readonly` | Private local anonymous commit history | 58 | 10 token-bearing wins, 36,649 estimated tokens saved, 10 correct raw refusals, 36 code-lens wins | Private local evidence only |

These totals are lane-specific. A win in one lane does not imply FlowTrim should
replace raw output, Atlas context economy, RTK, Ponytail, or Headroom globally.
The public README scoreboard is generated from sanitized reports and saved at
`benchmarks/results/2026-06-19-public-alpha.md`.

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

### Public Playground Read-Only

The `public-playground-readonly` profile is an adoption smoke suite. It uses
public-safe fake logs and code snippets built in memory, so contributors can run
it without private repositories, public corpus cache preparation, or network
cloning.

Scenarios tested:

- Python pytest failure log.
- npm/Vite noisy build pass.
- TypeScript type error.
- NestJS/Jest command output.
- Vite large-chunk build warning.
- Vue/TypeScript type-check command output.
- Dirty-before unchanged repo gate.
- Ticket-like commit churn synthetic repo.
- Git diff/stat exact-evidence refusal.
- Generated or lock-style control output.
- Small command where raw must win.
- Code-lens duplicate abstraction case.

Public playground totals:

- `token-bearing`: 9 cases, 8 wins, 2,826 estimated tokens saved.
- `refusal-correctness`: 2 cases, 2 correct refusals.
- `code-lens`: 1 case, 1 win.

Interpretation: this profile proves onboarding ergonomics and report hygiene. It
does not replace the pinned public corpus and does not support global benchmark
claims.

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

### Public Open-Source Read-Only

The `public-open-source-readonly` profile is the public benchmark corpus. It is
prepared from pinned Git commits listed in `benchmarks/public-corpus/manifest.v1.json`.
The prepare step may clone or fetch public repositories into a local cache; the
benchmark suite itself must run read-only against that cache.

What it tests:

- Public command-output cases from sanitized commit stat/numstat facts.
- Public code-lens cases from post-commit code blobs, reported only as
  complexity evidence.
- Public exact-evidence cases where raw must be selected.
- Public control cases for generated, lock, vendor, native, or config churn.

Totals from the latest local run:

- `token-bearing`: 26 cases, 22 wins, 2,412 estimated tokens saved, 22 skipped
  optional Headroom methods.
- `refusal-correctness`: 22 cases, 22 correct raw refusals.
- `code-lens`: 66 cases, 62 wins, 192 delete items, 133 duplicate
  abstractions, 1,414 generated LOC removed, 4 insufficient-evidence cases.

Interpretation: this profile supports claims only for the pinned public corpus
and measured lanes. It still does not prove FlowTrim globally beats RTK,
Ponytail, or Headroom.

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
Pre-existing dirty worktree state is allowed when the status remains unchanged
after the run; only post-run status changes block wins.

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
- `code-lens`: 36 cases, 36 wins.
- Delete-list items: 130.
- Duplicate abstractions: 105.
- Generated LOC delta: -975.

Interpretation: this supports the private local claim that FlowTrim can find
command-output and code-lens opportunities in historical Work commits without
changing repositories, while separating generated/lock-heavy commits as controls.
It does not support public or global benchmark claims.

Pre-existing dirty worktree state is represented with booleans and hashes only.
It does not block wins unless the post-run status differs from the pre-run
status.

### Work Dogfood Read-Only

The `work-dogfood-readonly` profile is private local evidence for real task or
ticket-shaped commit-history checks. Group selectors can be supplied locally,
but reports use only aliases such as `repo-01/group-01/commit-001`.

What it tests:

- Ticket/group-shaped slices of historical Work commits.
- Command-output compaction against aggregate commit stats.
- Exact-evidence raw selection for diff/stat-sensitive cases.
- Code-lens wins without token-saving claims.
- Dirty-before unchanged worktrees without treating them as runtime writes.

Sanitized latest local dogfood result:

- 144 cases across anonymous repo/group aliases.
- `token-bearing`: 32 wins, 2,845 estimated tokens saved.
- `refusal-correctness`: 32 correct raw refusals.
- `code-lens`: 62 wins and 18 insufficient-evidence cases.
- Runtime changes: none.
- Verification evidence: one backend-style Jest corpus passed; one Vue/Vite
  private Work corpus built successfully but type-check remained blocked by
  external project errors.

Interpretation: this supports private local dogfood confidence only. It does
not support public/global benchmark claims and must not expose repo names,
ticket IDs, commit messages, file paths, raw source, raw diffs, or raw logs.

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

Install editable package first:

```bash
python3 -m pip install -e .
```

Unit and invariant tests:

```bash
python3 -m unittest discover -s tests
```

Skill validation:

```bash
uv run --no-project --with PyYAML python <SKILL_CREATOR_QUICK_VALIDATE> skills/flowtrim
```

Public-safe synthetic proof:

```bash
flowtrim-benchmark suite --profile synthetic-heavy --format json
flowtrim-benchmark suite --profile public-playground-readonly --format json
flowtrim-benchmark docs-check --format json
flowtrim-benchmark public-corpus audit --manifest benchmarks/public-corpus/manifest.v1.json --format json
flowtrim-benchmark doctor --format json
```

Pinned public corpus prepare and proof:

```bash
flowtrim-benchmark public-corpus prepare --manifest benchmarks/public-corpus/manifest.v1.json --cache-root /tmp/flowtrim-public-corpus
flowtrim-benchmark suite --profile public-open-source-readonly --format json --public-corpus-manifest benchmarks/public-corpus/manifest.v1.json --public-cache-root /tmp/flowtrim-public-corpus > /tmp/flowtrim-public-baseline.json
```

Optional Headroom direct proof must stay ephemeral and direct-only:

```bash
HOME=/tmp/flowtrim-headroom-home XDG_CACHE_HOME=/tmp/flowtrim-headroom-cache HEADROOM_TELEMETRY=off uv run --no-project --with headroom-ai --with-editable . python -m flowtrim.cli.benchmark suite --profile public-open-source-readonly --format json --public-corpus-manifest benchmarks/public-corpus/manifest.v1.json --public-cache-root /tmp/flowtrim-public-corpus > /tmp/flowtrim-public-headroom.json
flowtrim-benchmark compare --baseline-report /tmp/flowtrim-public-baseline.json --candidate-report /tmp/flowtrim-public-headroom.json --focus headroom-direct --format markdown
```

Public alpha gates:

```bash
flowtrim-benchmark claim-check --report /tmp/flowtrim-public-baseline.json --claim "On the pinned public corpus, FlowTrim selected a safe lower-token method for measured lanes." --format json
flowtrim-benchmark privacy-scan --tracked --path /tmp/flowtrim-public-baseline.json --format json
flowtrim-benchmark release-check --report /tmp/flowtrim-public-baseline.json --unit-tests-passed --skill-validation-passed --benchmark-smoke-passed --privacy-scan-passed --sanitized-report-present --package-entrypoint-ready --license-reviewed --tool-versions-captured --format markdown
```

These gates are designed for public release hygiene. `claim-check` rejects
overclaims, `privacy-scan` rejects findings without printing local paths, and
`release-check` keeps release evidence explicit instead of assuming tests,
skill validation, license review, or tool-version evidence happened.
`doctor` is a read-only aggregate health check for package metadata, CLI smoke,
docs, skill shape, privacy scan, public manifest audit, and playground proof.

Vault proof with a local vault path:

```bash
flowtrim-benchmark suite --profile aql-vault-readonly --format json --aql-root <AQL_ATLAS_ROOT>
```

Private Work code-lens proof:

```bash
flowtrim-benchmark suite --profile work-code-readonly --format json --work-root <WORK_ROOT> --repo-limit 9 --files-per-repo 12
```

Private Work commit-history proof:

```bash
flowtrim-benchmark suite --profile work-commit-history-readonly --format json --work-repo <WORK_REPO_A> --work-repo <WORK_REPO_B>
```

Private Work dogfood proof:

```bash
flowtrim-benchmark suite --profile work-dogfood-readonly --format json --work-repo <WORK_REPO_A> --work-group <TICKET_OR_GROUP>
```

Privacy scan over tracked and untracked public repo files:

```bash
python3 - <<'PY'
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
- Headroom lost when it was skipped because no safe direct runner was available.
- Headroom direct won globally from a pinned-corpus result.
- Ponytail saved tokens without generated-token measurement.
- The vault is FlowTrim-safe while the verdict remains `hybrid-only`.
- Any claim that names private repos, exposes commit messages, quotes source, or
  quotes diff content.

## Public Release Gap

The public corpus closes the first public-evidence gap, but not the global
benchmark gap. Global claims still require a broader, representative corpus,
clear weighting rules, and Headroom direct measurements from an installed safe
direct runner. Until then, FlowTrim can publish synthetic fixture evidence,
pinned public-corpus evidence, and private Work runs only as local, anonymous,
aggregate evidence.

## Headroom Decision Rules

- If Headroom remains skipped, document unavailable/skipped behavior only.
- If Headroom measures but has zero safe wins, keep it as an optional baseline.
- If Headroom wins measured public-corpus lanes safely, allow it only as a
  lane-specific optional backend for those lanes.
- If Headroom emits marker-only output without retrieval, changes runtime state,
  stores raw output, or fails privacy gates, block adoption and require a
  retrieval-path proof before retesting.
