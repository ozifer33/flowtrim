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
   - `command-output`: run the command through `flowtrim-run -- <command>` (exit
     code is the pass/fail ground truth), or pipe existing output through
     `flowtrim-trim` with `--must-preserve` facts. Both emit a compact packet
     only when preservation and token gates pass and keep raw evidence otherwise.
   - `code-generation`: apply simplification pressure before adding code.
   - `long-context`: `flowtrim-trim --lane long-context` keeps trace/source/job
     ids, paths, and error labels auditable; raw wins when facts do not survive.
3. Select a method only when preservation, token, and wall-time gates pass.
4. Fall back to raw/default behavior when confidence is low. `--fallback excerpt`
   keeps a bounded head/tail/error-window excerpt instead of full raw output.

## Read When Needed

- For lane details, read `references/lane-policy.md`.
- For measurement gates, read `references/benchmark-gates.md`.
- For unsafe cases and fallback rules, read `references/safety-rules.md`.
- For benchmark, proof, and release-gate commands, read `references/commands.md`.

## Commands

- Run a command with trimmed output: `flowtrim-run -- npm test`
- Trim piped output (fail-safe): `npm test 2>&1 | flowtrim-trim`
- Trim a saved log with required facts: `flowtrim-trim --file /tmp/build.log --must-preserve "src/worker.py::test_retry_policy"`
- Inspect a trim decision with savings evidence: `flowtrim-trim --file /tmp/build.log --format json`
- Classify a task: `flowtrim-classify "task text"`
- Run public readiness doctor: `flowtrim-benchmark doctor --format json`

## Do Not Use When

- The user needs exact failing output, security evidence, line-level diff review, or source quotes.
- The task is a small factual answer with no token pressure.
- A tool would require hooks, proxy, MCP, memory, learning, telemetry, or persistent config changes without explicit approval.
