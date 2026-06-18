# FlowTrim Heavy Benchmark Lab Design

## Goal

Build a non-invasive benchmark lab that proves whether FlowTrim safely reduces
agent context for real work-repo flows, whether it beats or correctly defers to
RTK, Ponytail, and Headroom-style methods per lane, and whether any part of
FlowTrim should be used inside the Aql Atlas vault.

The lab must produce evidence strong enough to support a public-release decision:
use FlowTrim for main work only, use it in vault workflows, keep it as a hybrid
advisor, or defer release until gaps are fixed.

## Current Evidence

- FlowTrim v1 exists as a local private-first repo with core lane models,
  preservation checks, classifier, selector, runner, reporter, privacy scanner,
  Codex skill folder, and local verification.
- Latest FlowTrim verification passed: `PYTHONPATH=src python3 -m unittest
  discover -s tests` ran 33 tests successfully, and skill validation passed with
  `uv run --no-project --with PyYAML`.
- RTK is installed locally at `/opt/homebrew/bin/rtk`.
- Headroom is not currently installed as a CLI or Python package in this
  environment; Headroom comparisons must report `skipped` unless it is
  explicitly made available later.
- Aql short-command smoke benchmark showed raw output wins for empty/short
  commands: `git status --short` and `git diff --stat` had raw token count `0`,
  while RTK produced `1` token each. This validates the FlowTrim rule that short
  or no-output commands should stay raw.
- Existing Aql policy says semantic context economy comes first:
  `tools/aql.py packet`, `llm_brief`, source summaries, and generated indexes are
  the vault context layer. RTK is only a selected command-output helper.

## Non-Goals

- Do not install Headroom, enable `headroom wrap`, start a proxy, register MCP,
  enable memory/learn, or edit persistent config.
- Do not enable RTK hooks or any transparent command rewriting.
- Do not publish the repo or push to a public remote.
- Do not write private Work repo logs, production traces, customer data,
  secrets, `.env` values, or local private paths into fixtures or reports.
- Do not modify the Aql vault runtime policy based on benchmark output alone.
  The first deliverable is evidence and a verdict.

## Benchmark Lanes

### Command Output

Purpose: prove FlowTrim can save shell-output tokens when output is noisy, and
choose raw when output is short or exact evidence.

Methods:

- `raw`: unmodified output.
- `rtk`: real RTK command output when a safe command prefix exists.
- `flowtrim-selected`: FlowTrim selector decision over measured method results.

Required fixtures:

- short empty command output where raw must win.
- noisy build/test log with preserved file paths, failure labels, warnings, and
  summary lines.
- exact failing output where raw must win even if a compressed candidate is
  smaller.

### Long Context

Purpose: prove FlowTrim can evaluate auditable long-context compression without
hiding facts.

Methods:

- `raw`.
- `headroom-direct`: only if Headroom is available; otherwise `skipped`.
- `flowtrim-selected`.

Required fixtures:

- long JSON/tool trace with required IDs and paths.
- long handoff context with explicit requirements and non-goals.
- CCR-marker or marker-only candidate that must be marked unsafe unless a
  retrieve path is present.

### Code Generation

Purpose: evaluate Ponytail-style simplification pressure without pretending it
is command-output compression.

Methods:

- `baseline-code`: intentionally over-broad proposed code or diff metadata.
- `ponytail-lens`: delete-list and complexity pressure result.
- `flowtrim-selected`: FlowTrim code-generation lane recommendation.

Metrics:

- generated LOC delta.
- number of delete-list items.
- duplicate helper/abstraction count.
- test surface preserved.

This lane does not claim direct token savings unless generated text size is
measured separately. Its primary verdict is complexity reduction without
requirement loss.

### Exact Evidence

Purpose: prove FlowTrim refuses unsafe compression.

Methods:

- `raw`.
- unsafe smaller candidates.
- `flowtrim-selected`.

Pass condition: FlowTrim must select raw for security evidence, source quotes,
line-level diffs, failing stack traces, short commands, and explicit exact-output
requests.

### Vault Read-Only

Purpose: decide whether FlowTrim belongs inside Aql Atlas vault workflows.

Methods:

- Aql semantic context economy: packet, `llm_brief`, source summaries, generated
  indexes.
- selected RTK command-output helpers from Aql policy.
- FlowTrim lane recommendation and report.

Pass condition for vault adoption:

- FlowTrim must preserve Aql approval gates and source boundaries.
- FlowTrim must not recommend replacing `tools/aql.py packet`.
- FlowTrim may recommend selected command-output handling only when measured
  output beats raw and existing Aql policy.
- If evidence is mixed, verdict must be `hybrid only`: Atlas context economy for
  semantic retrieval, FlowTrim as a main-work/command-output advisor.

## Acceptance Gates

Every candidate method must pass these gates before it can count as a win:

- `candidate.tokens < raw.tokens`.
- candidate does not lose to the best safe lane method.
- preservation passes for paths, URLs, source IDs, errors, explicit
  requirements, and `must_preserve` facts.
- wall-time stays inside the lane budget.
- runtime changes are `none`.
- privacy scan finds no private paths or secret-like values in reports.
- exact-evidence lanes always choose raw.
- skipped methods are reported as skipped, not as wins or losses.
- reports include `insufficient-evidence` instead of positive savings when any
  guard is missing.

## Proposed Architecture

### Files

- `src/flowtrim/benchmark.py`: benchmark data models, fixtures loader, method
  runner, lane evaluator, and aggregate verdict logic.
- `src/flowtrim/adapters.py`: safe adapters for raw, RTK command-output, optional
  Headroom direct compression, and Ponytail-style code lens.
- `src/flowtrim/publication.py`: release-readiness and upgrade-gap scoring.
- `benchmarks/fixtures/`: public-safe synthetic logs, JSON, handoff text,
  exact-evidence examples, and code-generation examples.
- `benchmarks/reports/`: generated JSON/Markdown reports. Reports should be
  gitignored unless explicitly promoted.
- `tests/test_benchmark.py`: benchmark gates and lane comparisons.
- `tests/test_adapters.py`: adapter skip/fail-open behavior.
- `tests/test_publication.py`: public-release gate and upgrade backlog tests.
- `skills/flowtrim/scripts/flowtrim_benchmark_suite.py`: CLI wrapper that runs
  the suite and prints JSON or Markdown.

### Report Schema

The benchmark report should include:

- `schema`: `flowtrim-benchmark/v1`.
- `profile`: `synthetic-heavy`, `aql-vault-readonly`, or future profile name.
- `runtime_changes`: installs, hooks, proxy, MCP, config writes, telemetry, raw
  output storage.
- `tools`: availability and versions for RTK and Headroom.
- `cases`: lane, fixture, methods, tokens, wall-time, preservation result,
  selected method, winner, and decision reason.
- `strategy_totals`: raw total, FlowTrim-selected total, RTK total where
  applicable, Headroom total where applicable, and lane-specific savings.
- `vault_verdict`: `not-vault`, `hybrid-only`, `vault-safe`, or
  `insufficient-evidence`.
- `upgrade_backlog`: ordered list of public-release improvements.

## Heavy Test Strategy

The first suite should include at least:

- 3 command-output cases: short/no-output, noisy pass log, noisy failing log.
- 3 exact-evidence cases: source quote, failing stack trace, line-level diff.
- 2 long-context cases: JSON trace and handoff context.
- 2 code-generation cases: over-abstract helper and duplicate conversion logic.
- 2 vault read-only cases: Aql short-command raw win and Aql measured RTK-style
  command-output candidate.

The suite should also run mutation-like adversarial checks:

- remove a required path from a candidate and verify preservation fails.
- produce a smaller but slower candidate and verify raw wins.
- produce a smaller candidate with guard failure and verify report says
  `insufficient-evidence`.
- produce a Headroom unavailable state and verify the method is `skipped`.

## Vault Decision Rules

Use these decision labels:

- `not-vault`: FlowTrim loses or creates safety risk versus Atlas context economy.
- `hybrid-only`: FlowTrim helps command-output or main-work lanes, but Atlas
  packet/context economy remains vault default.
- `vault-safe`: FlowTrim wins on measured vault read-only cases without changing
  semantic retrieval or approval gates.
- `insufficient-evidence`: benchmark coverage is too narrow or a required tool is
  skipped.

Initial expectation from current evidence: `hybrid-only` or
`insufficient-evidence` is more likely than `vault-safe`. FlowTrim must earn a
vault recommendation through read-only benchmark results.

## Public-Release Upgrade Backlog

The benchmark lab should score these before public release:

- package entry points instead of requiring `PYTHONPATH=src`.
- CI command for tests, skill validation, benchmark smoke, and privacy scan.
- richer privacy scanner: tracked-file mode, ignored-cache skip, spaced env
  assignments, YAML-like secrets, `~/Documents/Work` shape.
- benchmark report examples with synthetic data only.
- documented Headroom unavailable behavior.
- RTK version/availability capture.
- Ponytail lens documentation that avoids claiming direct token compression.
- license/author metadata review before public publication.
- branch/default-branch and remote publication checklist.

## Success Criteria

The design is complete when the implementation can produce:

- a passing unit suite for benchmark/adapters/publication gates.
- a synthetic heavy benchmark report showing at least one FlowTrim win and at
  least one deliberate raw decision.
- an Aql vault read-only report with no runtime changes.
- a clear verdict on vault fit.
- a public-release upgrade backlog ranked by safety and usefulness.

The goal is not to force FlowTrim to win everywhere. The goal is to prove it wins
only when it should, refuses unsafe savings, and gives an honest verdict when the
old Atlas context economy is still better.

## Open Questions For Implementation Planning

- Should reports be tracked as fixtures or always generated and gitignored?
  Default: generate and gitignore, then promote only sanitized examples.
- Should Headroom remain optional for v1? Default: yes; no install without
  explicit approval.
- Should the Aql vault report live in FlowTrim or Aql Atlas? Default: generated
  in FlowTrim benchmark output, with no Aql file edits until user approval.
- Should Work repos be included now? Default: synthetic code-heavy fixtures
  first; real Work repos require explicit target approval because local metrics
  can reveal private paths.
