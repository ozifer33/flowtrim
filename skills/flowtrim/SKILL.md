---
name: flowtrim
description: Use when working in a software repository and token usage may grow because of noisy command output, test/build logs, search output, generated code, JSON/tool traces, handoff context, or uncertain tradeoffs between raw evidence and compression.
---

# FlowTrim

Use FlowTrim to choose the smallest safe context path for work-repo tasks.

## Route

1. Preserve the user objective, requirements, paths, commands, URLs, and evidence boundaries.
2. Classify the active flow:
   - `exact-evidence`: use raw output.
   - `repo-context`: read repo rules, README, scripts, and verification recipes first.
   - `command-output`: compare raw, measured command reduction, and deterministic reducers.
   - `code-generation`: apply simplification pressure before adding code.
   - `long-context`: use direct compression only when facts remain auditable.
3. Select a method only when preservation, token, and wall-time gates pass.
4. Fall back to raw/default behavior when confidence is low.

## Read When Needed

- For lane details, read `references/lane-policy.md`.
- For measurement gates, read `references/benchmark-gates.md`.
- For unsafe cases and fallback rules, read `references/safety-rules.md`.

## Commands

- Classify a task: `flowtrim-classify "task text"`
- Estimate fixture tokens: `flowtrim-benchmark "text"`
- Run synthetic proof: `flowtrim-benchmark suite --profile synthetic-heavy --format json`
- Run public playground proof: `flowtrim-benchmark suite --profile public-playground-readonly --format json`
- Audit pinned public manifest: `flowtrim-benchmark public-corpus audit --manifest benchmarks/public-corpus/manifest.v1.json --format json`
- Prepare pinned public corpus: `flowtrim-benchmark public-corpus prepare --manifest benchmarks/public-corpus/manifest.v1.json --cache-root /tmp/flowtrim-public-corpus`
- Run pinned public proof: `flowtrim-benchmark suite --profile public-open-source-readonly --public-corpus-manifest benchmarks/public-corpus/manifest.v1.json --public-cache-root /tmp/flowtrim-public-corpus --format json`
- Run private dogfood proof: `flowtrim-benchmark suite --profile work-dogfood-readonly --work-repo <WORK_REPO> --work-group <TICKET_OR_GROUP> --format json`
- Compare Headroom proof: `flowtrim-benchmark compare --baseline-report /tmp/flowtrim-public-baseline.json --candidate-report /tmp/flowtrim-public-headroom.json --focus headroom-direct --format markdown`
- Check a public claim: `flowtrim-benchmark claim-check --report /tmp/flowtrim-public-baseline.json --claim "On the pinned public corpus, FlowTrim selected a safe lower-token method for measured lanes." --format json`
- Run privacy gate: `flowtrim-benchmark privacy-scan --tracked --path /tmp/flowtrim-public-baseline.json --format json`
- Run docs gate: `flowtrim-benchmark docs-check --format json`
- Run public readiness doctor: `flowtrim-benchmark doctor --format json`
- Run release gate: `flowtrim-benchmark release-check --report /tmp/flowtrim-public-baseline.json --unit-tests-passed --skill-validation-passed --benchmark-smoke-passed --privacy-scan-passed --sanitized-report-present --package-entrypoint-ready --license-reviewed --tool-versions-captured --format markdown`
- Source checkout fallback: `PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py "text"`

## Do Not Use When

- The user needs exact failing output, security evidence, line-level diff review, or source quotes.
- The task is a small factual answer with no token pressure.
- A tool would require hooks, proxy, MCP, memory, learning, telemetry, or persistent config changes without explicit approval.
