# FlowTrim Final Native Core Design

## Summary

FlowTrim should become a standalone, clean-room native engine that can safely
reduce agent context without requiring RTK, Ponytail, or Headroom. Those tools
remain optional baselines and optional backends: FlowTrim may compare against
them, and may select one when it wins a measured lane safely, but FlowTrim must
not depend on them for basic operation.

The final product direction is:

1. Native command-output compactor.
2. Native code-complexity lens.
3. Native long-context packetizer.
4. Benchmark comparison against RTK, Ponytail-style behavior, and Headroom-style
   direct compression as optional baselines.

FlowTrim is not trying to win every case. It is trying to choose the smallest
safe context path, prove when a native method is better, and honestly fall back
to raw output or an external baseline when that is the better choice.

## Current State

The repo already has useful foundations:

- Lane classification for command output, code generation, long context, exact
  evidence, and repo context.
- Raw fallback and exact-evidence refusal behavior.
- Benchmark reports with `flowtrim-benchmark/v1` schema.
- Preservation, privacy, runtime-change, and claim gates.
- Synthetic, vault, private code-lens, and private commit-history profiles.
- Optional adapters for RTK, Headroom availability checks, and Ponytail-style
  code-lens behavior.
- Public-safe result documentation that separates publishable fixture evidence
  from private local evidence.

The repo is not final yet because the core reducers are still mostly benchmark
fixtures, conservative adapters, or early heuristics. FlowTrim needs native
engines that can stand alone, plus stronger comparison evidence before public or
global claims.

## Goals

### Product Goals

- FlowTrim works when installed alone.
- FlowTrim stays conservative: exact evidence, failing validation details,
  security evidence, line-level diffs, and source quotes use raw output.
- FlowTrim can optionally use RTK for noisy command output when RTK is available
  and passes preservation gates.
- FlowTrim can optionally compare against Ponytail-style complexity behavior
  without claiming direct token savings unless generated-token measurement is
  present.
- FlowTrim can optionally compare against Headroom-style direct compression when
  a safe read-only direct mode is available.
- FlowTrim can explain every decision in reports: raw, native, external
  baseline, skipped, or insufficient evidence.

### Proof Goals

- Every new native capability starts with failing tests.
- Every positive token claim is lane-specific.
- Native wins count only when token or complexity metrics improve while all
  preservation, wall-time, privacy, runtime, and claim gates pass.
- If an external baseline wins safely, FlowTrim reports that and keeps the
  external method as the selected optional backend for that lane.
- Private Work evidence remains anonymous, aggregate-only, and local.
- Public claims require a separate public open-source read-only corpus.

### Clean-Room Goals

- Do not copy code, prompts, private benchmark data, or implementation details
  from RTK, Ponytail, Headroom, or private Work repos.
- Derive implementation from FlowTrim specs, FlowTrim tests, public fixtures,
  and public documentation that is safe to cite.
- Keep a clean-room development log for native engines that records the
  requirement, test case, implementation rationale, and any external baseline
  used only for output comparison.

## Non-Goals

- Do not vendor RTK, Ponytail, or Headroom.
- Do not enable shell hooks, transparent command rewriting, wrap/proxy modes,
  MCP registration, memory, telemetry, or persistent config writes by default.
- Do not replace Atlas context economy for vault work. Vault remains
  `hybrid-only` until a dedicated vault-safe suite proves otherwise.
- Do not publish private Work repo names, paths, commit messages, raw diffs,
  raw source, or raw command output.
- Do not claim that FlowTrim globally beats RTK, Ponytail, or Headroom.

## Architecture

FlowTrim should be split into small units with explicit boundaries:

- `lane_policy`: classifies a task and states the allowed methods, forbidden
  methods, exact-evidence rules, wall-time budgets, and claim rules.
- `preservation`: extracts and checks must-keep facts such as paths, test ids,
  error labels, trace ids, source ids, requirement ids, and retrieve paths.
- `native_command`: produces compact command-output packets from noisy logs.
- `native_code_lens`: produces clean-room code-complexity recommendations and
  generated-token estimates.
- `native_context`: produces auditable long-context packets with source and
  retrieval anchors.
- `baselines`: wraps optional RTK, Ponytail-style, and Headroom-style
  comparisons without requiring installation or writing config.
- `benchmark`: runs public, private, vault, and baseline comparison suites.
- `publication`: validates allowed and forbidden claims before release or report
  publication.

The core decision pipeline is:

1. Classify the lane.
2. Extract required facts and exact-evidence boundaries.
3. Generate raw, native, and available optional baseline candidates.
4. Evaluate token or complexity metrics.
5. Run preservation, wall-time, privacy, runtime, and claim gates.
6. Select the safest winner, raw fallback, or `insufficient-evidence`.
7. Store only sanitized report data.

## Native Command-Output Compactor

The command-output compactor targets noisy test, build, lint, package, and search
logs. It should produce a structured packet instead of a vague summary.

Required packet fields:

- `status`: pass, fail, warning, mixed, or unknown.
- `primary_files`: sanitized paths or path-family labels from public fixtures or
  private aliases.
- `failing_tests`: test ids or aliases when present.
- `error_labels`: exception names, error codes, or validation labels.
- `summary_lines`: short human-readable findings.
- `omitted_noise_classes`: repeated progress, duplicate warnings, stack repeats,
  cache chatter, or generated churn.
- `must_keep`: facts the selector required and verified.
- `content_hash`: hash of the raw input.

It wins only when:

- The packet has fewer estimated tokens than raw output.
- Every must-keep fact is preserved.
- Exact-output lanes are not compacted.
- Wall-time is within the lane budget.
- Privacy scan passes on the packet.
- The report stores no raw private output.

RTK remains an optional command-output baseline. FlowTrim can select RTK when RTK
wins safely, but native command-output becomes the default only after public and
private aggregate suites show it is at least as safe and better on the selected
scorecard.

## Native Code-Complexity Lens

The code lens targets agent coding behavior before code generation or during
review. It should reduce unnecessary generated code, not merely compress text.

Required outputs:

- `delete_items`: specific removable abstractions or duplicate logic.
- `merge_items`: repeated conversions, wrappers, or helper layers that can be
  merged.
- `must_keep_items`: requirement or test-surface items that block deletion.
- `generated_loc_delta`: estimated generated LOC change.
- `generated_token_delta`: estimated generated-token change when the planned
  output is measurable.
- `requirement_affected`: requirement id or `none`.
- `test_surface_affected`: test id/path or `none`.
- `confidence`: deterministic confidence label derived from visible evidence.

It wins only when:

- Complexity decreases.
- Requirement surface is preserved.
- Test surface is preserved.
- Must-keep rules are preserved.
- A generated-token claim is present only when generated-token measurement exists.

Ponytail-style behavior remains a baseline label and comparison target. FlowTrim
does not need Ponytail installed to run this lane, and it must not claim
"Ponytail saved tokens" from code-lens results.

## Native Long-Context Packetizer

The long-context packetizer targets trace JSON, handoffs, tool traces, and large
audit contexts. It should preserve auditable anchors rather than produce a loose
summary.

Required packet fields:

- `context_type`: trace, handoff, packet, audit, or unknown.
- `anchors`: trace ids, job ids, source ids, requirement ids, retrieve paths, and
  source paths when present.
- `facts`: failure facts, constraints, decisions, and next actions.
- `retrieval_plan`: where raw evidence can be retrieved if exact detail is
  needed.
- `omitted_sections`: repeated or low-signal sections removed.
- `content_hash`: hash of the raw input.

It wins only when:

- Anchors and failure facts are preserved.
- A retrieval path exists for omitted exact evidence.
- Marker-only context without retrieval remains `insufficient-evidence`.
- Wall-time and privacy gates pass.

Headroom remains optional. If Headroom is unavailable, it is skipped neutrally.
If a safe direct read-only Headroom mode is available later, it can be tested as
a baseline. Wrap, proxy, MCP, config, memory, and install behavior remain outside
the default scope.

## Benchmark Design

FlowTrim needs four benchmark families before it can be treated as final:

1. `synthetic-heavy`: public-safe fixtures for exact behavior and mutations.
2. `public-open-source-readonly`: public repos and public commits for publishable
   external comparisons.
3. `work-code-readonly` and `work-commit-history-readonly`: private local
   aggregate-only evidence.
4. `aql-vault-readonly`: vault fit and Atlas deferral evidence.

Each report must compare:

- raw
- FlowTrim native
- available optional baselines
- selected method

Each report must include:

- runtime changes
- tool availability and versions when available
- cases
- metric totals
- vault verdict when relevant
- upgrade backlog
- claim validation status

## Better-Than Scorecard

Native methods are better than an external baseline only for a measured lane when
all required gates pass and at least one primary score improves.

Primary scores:

- Command output: estimated output tokens saved.
- Code lens: generated complexity reduction and generated-token reduction when
  measurable.
- Long context: estimated input tokens saved while preserving anchors and
  retrieval.
- Exact evidence: correct refusal and raw selection.

Guard scores:

- Preservation pass rate.
- Wall-time budget pass rate.
- Privacy findings count.
- Runtime-change findings count.
- Correct skipped-tool handling.
- Claim validator pass rate.

Decision labels:

- `native-win`: FlowTrim native wins all gates and primary score.
- `baseline-win`: optional external baseline wins safely.
- `raw-win`: raw is safer, cheaper, exact, or faster.
- `insufficient-evidence`: a required fact, guard, tool version, or retrieval path
  is missing.
- `skipped-neutral`: a tool was unavailable or intentionally not tested.

## Release Policy

FlowTrim can be used privately as a conservative skill before public release.
Public release needs stronger gates:

- Unit tests pass.
- Skill validation passes.
- Synthetic benchmark passes.
- Public open-source benchmark exists and passes privacy scan.
- Private Work reports remain local-only and aggregate-only.
- Tool versions are captured for available tools.
- Package entry points work without requiring manual path setup.
- CI runs tests, benchmark smoke, skill validation, and privacy scan.
- License, author metadata, attribution, and clean-room log are reviewed.
- Sanitized public example reports are present.

Allowed public claims must remain narrow:

- FlowTrim selected a safe lower-token method for measured lanes.
- FlowTrim correctly selected raw for unsafe exact-evidence lanes.
- FlowTrim native command-output compactor beat the measured baseline on the
  stated public corpus, if and only if the public corpus proves it.
- FlowTrim code lens reduced generated complexity without claiming token savings
  unless generated-token measurement exists.
- Headroom was skipped when unavailable.

Forbidden claims remain:

- FlowTrim globally beats RTK, Ponytail, and Headroom.
- Headroom lost when skipped.
- Ponytail saved tokens without generated-token measurement.
- FlowTrim is vault-safe while the vault verdict is `hybrid-only`.
- Private Work evidence is a public benchmark.

## Implementation Phases

### Phase 1: Scorecard And Native Candidate Interfaces

Create shared interfaces for native candidate packets and scorecard decisions.
This phase should not change default behavior. It prepares comparison reporting
and makes current decisions easier to audit.

Proof:

- Unit tests for score labels.
- JSON schema tests for native candidate packets.
- No benchmark regression.

### Phase 2: Native Command-Output Compactor

Implement a clean-room command-output packetizer for public-safe logs. Wire it
into `synthetic-heavy` beside raw and RTK.

Proof:

- Failing tests for noisy pass, noisy fail, missing path, slower candidate, guard
  failure, and exact-output refusal.
- Benchmark compares raw, RTK, and native.
- Native may become selected only when it beats raw and RTK safely.

### Phase 3: Native Code-Complexity Lens

Implement a clean-room lens that detects duplicate conversion logic,
over-abstract wrappers, unused helper candidates, and blocked must-keep cases.

Proof:

- Tests for safe delete-list wins.
- Tests that requirement/test-surface impact blocks wins.
- Tests that generated-token claims require generated-token measurement.
- Private Work aggregate reports remain anonymous.

### Phase 4: Native Long-Context Packetizer

Implement an auditable packetizer for traces and handoffs.

Proof:

- Tests for trace id, job id, source id, requirement id, retrieve path, and
  failure facts.
- Marker-only unsafe context remains `insufficient-evidence`.
- Headroom skipped remains neutral unless a safe direct baseline is available.

### Phase 5: Public Open-Source Read-Only Corpus

Add public repos and public commit fixtures or manifest-driven read-only runs.

Proof:

- Reports contain public-safe paths or aliases only as configured.
- No private data appears.
- Claims from this corpus are allowed only when report evidence supports them.

### Phase 6: Release Hardening

Add CLI entry points, CI commands, sanitized example reports, clean-room log,
license review checklist, and public claim checks.

Proof:

- Package entry points run without manual path setup.
- CI covers tests, skill validation, benchmark smoke, and privacy scan.
- Release readiness has no blockers for the intended release tier.

## Error Handling

FlowTrim should prefer visible conservative failure over silent risky wins:

- Missing must-keep fact: `insufficient-evidence`.
- Missing retrieval path for omitted exact context: `insufficient-evidence`.
- Tool unavailable: `skipped-neutral`.
- Tool available without version: release blocker.
- Runtime change detected: no token claim, release blocker.
- Privacy finding: report blocked.
- Exact-evidence lane: raw selection.
- Candidate over wall-time budget: raw selection unless another safe candidate
  wins within budget.

## Documentation Updates

The implementation should update:

- `README.md`: standalone mode, optional RTK mode, and final native direction.
- `docs/benchmark-results.md`: native-vs-baseline evidence once benchmarks
  exist.
- `skills/flowtrim/SKILL.md`: route rules for native methods and optional
  baselines.
- `NOTICE.md`: keep clean-room and attribution language clear.
- New clean-room log: record native behavior sources as FlowTrim specs and tests.

## Open Decisions Resolved

- RTK is kept as optional accelerator for command output until native wins
  safely.
- Ponytail remains a complexity baseline label, not a token-saving dependency.
- Headroom remains optional and skipped unless safe direct read-only testing is
  explicitly available.
- Atlas remains the default vault context economy.
- Public/global claims wait for the public open-source corpus.

## Success Criteria

The final direction is achieved when:

- FlowTrim works alone in every lane with conservative fallback behavior.
- FlowTrim can optionally compare against RTK, Ponytail-style behavior, and
  Headroom-style direct compression.
- Native command-output, code-lens, and long-context methods each have tests,
  benchmarks, and sanitized reports.
- Native methods become defaults only after the scorecard proves they beat raw
  and optional baselines safely for the relevant lane.
- Reports never leak private data and never overclaim.
- Public release gates pass for the intended release tier.
