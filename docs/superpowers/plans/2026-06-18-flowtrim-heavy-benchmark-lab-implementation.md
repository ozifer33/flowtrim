# FlowTrim Heavy Benchmark Lab Implementation Plan

## Objective

Implement the FlowTrim heavy benchmark lab described in
`docs/superpowers/specs/2026-06-18-flowtrim-heavy-benchmark-lab-design.md`.

The implementation must prove, with local tests and generated evidence, whether
FlowTrim safely reduces context for main work, whether it beats or correctly
defers to RTK, Ponytail-style code simplification, and Headroom-style long
context handling per lane, and whether Aql Atlas vault workflows should keep the
existing Atlas context economy as the default.

## Constraints

- Do not install Headroom or enable Headroom wrap/proxy/MCP/config/memory.
- Do not enable RTK hooks or transparent shell rewriting.
- Do not publish or push the repo.
- Do not store raw private Aql source bodies, Work repo output, secrets, `.env`
  values, `.codex` paths, or local home paths in tracked files or
  promoted reports.
- Generate benchmark reports under ignored `benchmarks/reports/` by default.
- Aql vault checks are read-only and must not modify Aql policy or source files.
- Tests come first for each implementation slice.

## Files To Add Or Change

- Add `src/flowtrim/benchmark.py`.
- Add `src/flowtrim/adapters.py`.
- Add `src/flowtrim/publication.py`.
- Add public-safe fixtures under `benchmarks/fixtures/`.
- Add ignored report directory rule for `benchmarks/reports/`.
- Extend `skills/flowtrim/scripts/flowtrim_benchmark.py` with a `suite` mode.
- Add tests:
  - `tests/test_benchmark.py`
  - `tests/test_adapters.py`
  - `tests/test_publication.py`
  - update existing tests only if a public API change requires it.
- Update `README.md` with the benchmark-lab command and interpretation rules.

## Verification Commands

Run these after each meaningful slice:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Run these before completion:

```bash
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile synthetic-heavy --format json
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile aql-vault-readonly --format json --aql-root <AQL_ATLAS_ROOT>
uv run --no-project --with PyYAML python <SKILL_CREATOR_QUICK_VALIDATE> skills/flowtrim
python3 - <<'PY'
from pathlib import Path
from flowtrim.privacy import scan_text
findings = {}
for path in Path(".").rglob("*"):
    if (
        ".git" in path.parts
        or "__pycache__" in path.parts
        or not path.is_file()
        or path.suffix == ".pyc"
        or ("benchmarks" in path.parts and "reports" in path.parts)
    ):
        continue
    text = path.read_text(errors="ignore")
    hits = scan_text(text)
    if hits:
        findings[str(path)] = hits
print(findings)
raise SystemExit(1 if findings else 0)
PY
```

The final privacy command is expected to pass for tracked/public files. Generated
local reports can be scanned separately before any promotion.

## Task 1: Benchmark Schema And Gate Logic

### Tests First

Create `tests/test_benchmark.py` with cases that assert:

- A token-bearing candidate only counts as a win when it has fewer tokens than
  raw, passes preservation, passes guard checks, does not time out, and stays
  under the lane wall-time budget.
- Short or zero-token raw command output wins over any non-raw candidate.
- Exact-evidence cases always select raw even when an unsafe candidate is
  smaller.
- Skipped methods are represented as skipped and cannot be selected.
- Guard failure produces `insufficient-evidence`, not positive savings.
- Vault semantic cases defer to `atlas-context-economy` and produce a
  `hybrid-only` verdict unless every required vault family passes.
- Report JSON contains `schema`, `profile`, `runtime_changes`, `tools`, `cases`,
  `metric_totals`, `vault_verdict`, and `upgrade_backlog`.

### Implementation

Add `src/flowtrim/benchmark.py` with these public structures and functions:

- `BenchmarkStatus`: `ok`, `skipped`, `failed`, `timeout`,
  `insufficient-evidence`, `selected`.
- `MetricFamily`: `token-bearing`, `code-lens`, `refusal-correctness`,
  `vault-semantic`.
- `RuntimeChanges`: booleans for installs, hooks, proxy, MCP, config writes,
  telemetry, stores raw output, and unapproved filesystem writes. Include
  `is_none`.
- `ToolInfo`: tool name, available boolean, optional version, optional reason.
- `MethodMeasurement`: method, status, tokens, wall time, timeout, repeat count,
  guard passed, optional reason, optional payload.
- `PreservationSummary`: passed boolean and missing item list.
- `BenchmarkCase`: case id, lane, fixture, metric family, methods,
  preservation, runtime changes, selected method, winner, counts-as-claim,
  decision reason.
- `BenchmarkReport`: schema, profile, runtime changes, tools, cases,
  metric totals, vault verdict, upgrade backlog.
- `evaluate_case(case)`: applies lane gates and fills selected/winner/reason.
- `build_report(profile, cases, tools, upgrade_backlog)`: computes totals and
  vault verdict.
- `report_to_json(report)`: stable sorted JSON serialization.

Implementation rules:

- Reuse `Lane` from `src/flowtrim/models.py`.
- Use `LANE_WALL_TIME_BUDGET_MS` from `selector.py` where possible, with a
  benchmark override for vault read-only of 15000 ms.
- Do not remove or weaken existing `select_best_method`.
- Exact-evidence raw refusal is success, not insufficient evidence.
- A skipped method never counts as a loss or a win.
- `counts_as_claim` is false when the selected method is raw due to safety,
  when evidence is insufficient, or when a tool is skipped.

## Task 2: Safe Adapters

### Tests First

Create `tests/test_adapters.py` with deterministic tests for:

- `raw_adapter` returns token count, zero wall-time, repeat count, and preserved
  content hash.
- `rtk_adapter` reports skipped when the executable is not found.
- `rtk_adapter` can be tested with an injected command runner and never enables
  hooks or rewrites commands.
- `headroom_adapter` reports skipped when unavailable and never tries to install
  or configure Headroom.
- `ponytail_lens` returns delete-list items using the required schema and flags
  `must_keep_violation` when a fixture marks a required behavior/test surface.
- Median wall-time and timeout fields are present for repeated fixture methods.

### Implementation

Add `src/flowtrim/adapters.py` with:

- `RawAdapter.measure(text, lane, repeat_count=3)`.
- `RTKAdapter.measure(text, lane, executable=None, runner=None)`.
- `HeadroomAdapter.measure(text, lane, executable=None)`.
- `PonytailLens.analyze(text, must_keep=(), tests=())`.
- `median_measure(callable, repeat_count, timeout_ms)` helper.
- `hash_text(text)` helper that returns a short SHA-256 digest for reports.

Implementation rules:

- Adapters operate on strings and fixture content by default.
- Live command execution is opt-in through an injected runner or an approved
  suite function.
- RTK and Headroom unavailable states are `skipped`, not failures.
- Headroom adapter must not run any command except version/availability checks.
- Ponytail lens is deterministic and conservative; if unsure, emit `watch`
  rather than `must-delete`.

## Task 3: Public-Safe Fixtures

### Tests First

Add tests in `tests/test_benchmark.py` or `tests/test_publication.py` that scan
all files under `benchmarks/fixtures/` with `flowtrim.privacy.scan_text` and
assert no findings.

### Implementation

Create fixtures:

- `benchmarks/fixtures/logs/short-empty.txt`
- `benchmarks/fixtures/logs/noisy-build-pass.txt`
- `benchmarks/fixtures/logs/noisy-build-fail.txt`
- `benchmarks/fixtures/exact/source-quote.txt`
- `benchmarks/fixtures/exact/failing-stack-trace.txt`
- `benchmarks/fixtures/exact/line-level-diff.txt`
- `benchmarks/fixtures/context/tool-trace.json`
- `benchmarks/fixtures/context/handoff.md`
- `benchmarks/fixtures/code/over-abstract-helper.txt`
- `benchmarks/fixtures/code/duplicate-conversion-logic.txt`
- `benchmarks/fixtures/vault/aql-short-command.txt`
- `benchmarks/fixtures/vault/aql-rtk-candidate.txt`
- `benchmarks/fixtures/vault/aql-packet-routing.md`
- `benchmarks/fixtures/vault/aql-index-inventory.md`
- `benchmarks/fixtures/vault/aql-source-id-preservation.md`
- `benchmarks/fixtures/vault/aql-approval-boundary.md`

Fixture rules:

- Synthetic content only.
- Use fake paths like `src/example.py`, not local absolute paths.
- Use fake source IDs like `source:demo-001`.
- Include explicit `must_preserve` markers where gate tests need them.
- Include enough repeated/noisy lines to make token-bearing reductions possible.

## Task 4: Suite Runner

### Tests First

Add benchmark tests that call the suite builder directly and assert:

- `synthetic-heavy` includes at least 3 command-output, 3 exact-evidence,
  2 long-context, and 2 code-generation cases.
- `aql-vault-readonly` includes 6 vault cases and no runtime changes.
- Synthetic report has at least one safe lower-token win and one deliberate raw
  exact-evidence decision.
- Headroom unavailable is skipped, not counted as a loss.
- Mutation checks cover missing path, smaller-but-slower candidate, guard
  failure, and Headroom skipped.

### Implementation

In `src/flowtrim/benchmark.py`, add:

- `load_fixture(path)`.
- `build_synthetic_heavy_suite(fixtures_root)`.
- `build_aql_vault_readonly_suite(fixtures_root, aql_root=None)`.
- `run_suite(profile, fixtures_root=None, aql_root=None)`.

Suite behavior:

- Fixture replay is default and stores only token counts, hashes, method names,
  sanitized snippets, and verdicts.
- Aql live mode is optional and read-only. It may run only approved commands:
  `git status --short`, `git diff --stat`, and Aql inventory/packet commands
  that are explicitly coded as read-only. If a command is unavailable or times
  out, the case is `insufficient-evidence`, not a win.
- Pre/post `git status --short` must be captured for live repo checks. If there
  are unapproved new files or changes caused by the suite, fail the case.
- Do not run the full Aql validation loop in the benchmark suite.

## Task 5: Publication And Upgrade Gate

### Tests First

Create `tests/test_publication.py` with cases that assert:

- Public release is blocked if tests, skill validation, benchmark smoke, or
  privacy scan evidence is missing.
- A tracked/generated report with private findings blocks release.
- Package entrypoint gaps become upgrade backlog items, not false passes.
- Allowed and forbidden claim language are enforced.
- Vault `hybrid-only` is acceptable evidence; it must not be rewritten as
  `vault-safe`.

### Implementation

Add `src/flowtrim/publication.py` with:

- `ReleaseEvidence`: unit tests passed, skill validation passed, benchmark smoke
  passed, privacy scan passed, sanitized report present, package entrypoint
  ready, license reviewed, tool versions captured.
- `ReleaseReadiness`: ready boolean, blockers, backlog, allowed claims,
  forbidden claims.
- `assess_release_readiness(report, evidence)`.
- `validate_claim(report, claim)`.

Rules:

- Missing Headroom is a backlog item and claim limiter, not a release pass for
  "beat Headroom".
- Ponytail lens can claim complexity reduction only when code-lens metrics pass.
- Token-savings claims must be lane-specific.

## Task 6: CLI And Skill Wrapper

### Tests First

Add a small subprocess test or direct function test that invokes the wrapper
with `suite --profile synthetic-heavy --format json` and checks valid JSON.

### Implementation

Extend `skills/flowtrim/scripts/flowtrim_benchmark.py`:

- Keep existing behavior for the current positional text mode.
- Add subcommand:

```bash
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite \
  --profile synthetic-heavy \
  --format json
```

Options:

- `--profile synthetic-heavy|aql-vault-readonly`
- `--format json|markdown`
- `--aql-root PATH`
- `--reports-dir PATH` optional, default `benchmarks/reports`
- `--write-report` optional; when omitted, print only.

Rules:

- Writing reports goes only to ignored `benchmarks/reports/` unless an explicit
  path is supplied.
- JSON output must be privacy-safe by schema.
- Markdown output must not include raw private output.

## Task 7: Documentation And Git Hygiene

### Tests First

Run privacy tests after docs updates.

### Implementation

- Add `benchmarks/reports/` to `.gitignore`.
- Update `README.md` with:
  - what FlowTrim can claim.
  - benchmark commands.
  - why vault result is expected to be `hybrid-only` unless all read-only
    families pass.
  - Headroom unavailable behavior.
  - Ponytail lens is complexity analysis, not token compression.

## Task 8: Run Evidence And Review

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile synthetic-heavy --format json
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile aql-vault-readonly --format json --aql-root <AQL_ATLAS_ROOT>
uv run --no-project --with PyYAML python <SKILL_CREATOR_QUICK_VALIDATE> skills/flowtrim
```

Then run privacy scan over tracked/public files and, if reports are written, over
the generated report.

Request a code review after implementation. Fix every Important/Critical issue.
Commit only after tests, benchmark smoke, skill validation, and privacy scan pass.

## Expected Final Verdict

The implementation should produce an honest verdict:

- Main work: FlowTrim can be recommended where measured token-bearing lanes win
  and exact-evidence lanes refuse compression.
- Vault: likely `hybrid-only` unless the read-only suite proves every vault
  family passes. Atlas packet/context economy remains default for semantic vault
  retrieval.
- Public release: allowed after release blockers pass; backlog remains for CI,
  package entrypoints, richer privacy scan, richer Headroom integration, and
  public example reports.
