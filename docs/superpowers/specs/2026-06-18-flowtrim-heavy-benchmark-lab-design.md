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
- If evidence is mixed, verdict must be `hybrid-only`: Atlas context economy for
  semantic retrieval, FlowTrim as a main-work/command-output advisor.

## Acceptance Gates

Every candidate method must pass the gates for its metric family before it can
count as a win:

- Token-bearing lanes: `candidate.tokens < raw.tokens`, and the candidate does
  not lose to the best safe lane method.
- Code-generation lane: delete-list and complexity metrics improve without
  requirement loss, test-surface loss, or `must_keep_violation`.
- Exact-evidence lane: raw refusal is the win condition; smaller compressed
  candidates must not count as wins.
- Vault semantic cases: correctly defer to Atlas packet/context economy when
  semantic routing is safer than compression.
- preservation passes for paths, URLs, source IDs, errors, explicit
  requirements, and `must_preserve` facts.
- wall-time stays inside the lane budget.
- runtime changes are `none`.
- privacy scan finds no private paths, local workspace roots, `.codex` paths,
  `.env` values, Work paths, unsanitized Aql evidence, or secret-like values in
  fixtures or reports.
- exact-evidence lanes always choose raw.
- skipped methods are reported as skipped, not as wins or losses.
- reports include `insufficient-evidence` instead of positive savings when any
  guard is missing.

## Runtime Audit Contract

Benchmark execution must prove the non-invasive claim, not merely report it.

- Fixture replay is the default. Live commands are allowed only from an explicit
  read-only whitelist such as `git status --short`, `git diff --stat`, selected
  `find` inventory commands, and approved Aql read-only token commands.
- Live commands must run with explicit timeouts and captured stdout/stderr.
- Where possible, live command comparisons run in temporary directories or
  read-only repo views. Commands that might write cache, metrics, tee files,
  build output, package state, or config are forbidden in v1.
- The runner records pre/post `git status --short` for each live repo. Any new
  tracked or unignored file outside approved generated report paths fails the
  case.
- The runner monitors known sensitive/config paths in report metadata:
  `.codex/`, `.rtk/`, Headroom config, shell init files, MCP config, and
  benchmark report directories.
- Generated reports are local-only by default and live under ignored
  `benchmarks/reports/`. A report can be promoted only after privacy scan and
  explicit human review.
- The report must include `runtime_changes` with concrete booleans for installs,
  hooks, proxy, MCP, config writes, telemetry, raw output storage, and
  unapproved filesystem writes.

## Privacy And Redaction Gate

Privacy is release-blocking, not a later polish item.

- Do not store raw private command output. Store hashes, token counts, method
  names, and sanitized snippets only when a fixture is public-safe.
- Fail the benchmark if any fixture, generated report, or promoted example
  contains `/Users/...`, the active workspace root, `.codex`, `.env`,
  `Documents/Work`, secret-like assignments, production/customer data, or
  unsanitized Aql raw evidence.
- Aql vault read-only reports must not copy source bodies or private local paths.
  They may store stable source IDs, wiki paths, command names, hashes, aggregate
  tokens, and verdicts.
- Public-release claims require a clean privacy scan over tracked files and any
  report proposed for publication.

## Wall-Time Measurement Contract

Wall-time gates must be deterministic enough to compare methods fairly.

- Default lane budgets:
  - command-output: 250 ms per fixture replay, 2 seconds per live read-only
    command.
  - long-context: 500 ms for fixture replay.
  - code-generation lens: 500 ms for deterministic fixture analysis.
  - exact-evidence: raw only; compression candidates are not timed as winners.
  - vault-readonly: 15 seconds per approved Aql live command.
- Fixture methods run at least 3 times and report median wall-time. Live Aql
  commands run once by default to avoid long-running validation loops.
- Timeout means the method is invalid for that case, except raw exact evidence
  fallback remains the safety baseline.
- Reports must include `wall_time_ms`, `timeout`, and `repeat_count`.

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
- `skills/flowtrim/scripts/flowtrim_benchmark.py`: extend the existing wrapper
  with a `suite` mode that runs the benchmark lab and prints JSON or Markdown.
  Add a separate `flowtrim_benchmark_suite.py` only if the implementation plan
  shows the existing wrapper would become confusing.

### Report Schema

The benchmark report should include:

- `schema`: `flowtrim-benchmark/v1`.
- `profile`: `synthetic-heavy`, `aql-vault-readonly`, or future profile name.
- `runtime_changes`: installs, hooks, proxy, MCP, config writes, telemetry, raw
  output storage.
- `tools`: availability and versions for RTK and Headroom.
- `cases`: lane, fixture, methods, tokens, wall-time, preservation result,
  selected method, winner, and decision reason.
- `metric_totals`: lane-specific totals grouped by metric family:
  token-bearing lanes (`command-output`, `long-context`), code lens metrics
  (`generated_loc`, `delete_items`, `duplicate_abstractions`), and
  refusal-correctness metrics (`exact-evidence` raw decisions).
- `vault_verdict`: `not-vault`, `hybrid-only`, `vault-safe`, or
  `insufficient-evidence`.
- `upgrade_backlog`: ordered list of public-release improvements.

Example case record:

```json
{
  "case_id": "command-output/noisy-build-pass",
  "lane": "command-output",
  "fixture": "benchmarks/fixtures/logs/noisy-build-pass.txt",
  "methods": {
    "raw": {
      "status": "ok",
      "tokens": 1200,
      "wall_time_ms": 0,
      "timeout": false,
      "repeat_count": 3
    },
    "rtk": {
      "status": "ok",
      "tokens": 520,
      "wall_time_ms": 180,
      "timeout": false,
      "repeat_count": 3
    },
    "headroom": {"status": "skipped", "reason": "not installed"},
    "flowtrim-selected": {"status": "selected", "method": "rtk"}
  },
  "preservation": {"passed": true, "missing": []},
  "runtime_changes": {
    "installs": false,
    "hooks": false,
    "proxy": false,
    "mcp": false,
    "config_writes": false,
    "telemetry": false,
    "stores_raw_output": false,
    "unapproved_filesystem_writes": false
  },
  "winner": "rtk",
  "counts_as_claim": true
}
```

## Ponytail Lens Schema

Ponytail-style results must be deterministic enough to test. Each delete-list
item must include:

- `item`: short name of the code or abstraction to remove.
- `severity`: `must-delete`, `should-delete`, or `watch`.
- `rationale`: why it is unnecessary or duplicated.
- `estimated_loc_delta`: positive or negative line estimate.
- `requirement_affected`: requirement ID or `none`.
- `test_surface_affected`: test name/path or `none`.
- `must_keep_violation`: true if deleting it would violate a requirement,
  preservation fact, or test surface.

The lens passes only when all `must-delete` and `should-delete` recommendations
avoid `must_keep_violation`, preserve required behavior, and keep the planned
test surface intact.

## Heavy Test Strategy

The first suite should include at least:

- 3 command-output cases: short/no-output, noisy pass log, noisy failing log.
- 3 exact-evidence cases: source quote, failing stack trace, line-level diff.
- 2 long-context cases: JSON trace and handoff context.
- 2 code-generation cases: over-abstract helper and duplicate conversion logic.
- 6 vault read-only cases:
  - Aql short-command raw win.
  - Aql measured RTK-style command-output candidate.
  - packet or `llm_brief` semantic routing case.
  - generated index/report inventory case.
  - source-ID preservation case.
  - approval/sensitivity boundary case.

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
- `vault-safe`: FlowTrim wins where token-bearing handling applies, and
  correctly defers to Atlas packet/context economy where semantic routing is the
  safe default, across all required vault read-only case families.
- `insufficient-evidence`: benchmark coverage is too narrow or a required tool is
  skipped.

Initial expectation from current evidence: `hybrid-only` or
`insufficient-evidence` is more likely than `vault-safe`. FlowTrim must earn a
vault recommendation through read-only benchmark results.

## Public-Release Upgrade Backlog

The benchmark lab should score these before public release:

Release-blocking gates:

- clean unit suite, skill validation, benchmark smoke, and privacy scan.
- package entry points or documented `PYTHONPATH=src` limitation.
- sanitized benchmark example report with synthetic data only.
- RTK and Headroom availability/version capture.
- license/author metadata review.
- no tracked generated reports that contain local paths or raw private output.

Upgrade backlog:

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

## Claim Language

Allowed claims:

- "FlowTrim selected a safe lower-token method for this measured lane."
- "FlowTrim correctly chose raw because compression was unsafe or not cheaper."
- "Headroom was skipped because it was unavailable."
- "Ponytail lens reduced code complexity in this fixture without claiming direct
  command-output compression."
- "Vault verdict is `hybrid-only` unless all vault read-only case families pass."

Forbidden claims:

- "FlowTrim beats RTK, Ponytail, and Headroom globally."
- "FlowTrim is vault-safe" from command-output cases alone.
- "Headroom lost" when Headroom was unavailable or skipped.
- "Ponytail saved tokens" unless generated text size was directly measured.
- "No runtime changes" without the runtime audit evidence above.

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
- Should the existing `flowtrim_benchmark.py` wrapper be extended or should a new
  `flowtrim_benchmark_suite.py` be added? Default: extend the existing wrapper
  with a `suite` subcommand unless the implementation plan shows the wrapper
  would become confusing.
