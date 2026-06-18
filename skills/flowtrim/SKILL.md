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

- Classify a task: `PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_orchestrator.py "task text"`
- Estimate fixture tokens: `PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py "text"`

## Do Not Use When

- The user needs exact failing output, security evidence, line-level diff review, or source quotes.
- The task is a small factual answer with no token pressure.
- A tool would require hooks, proxy, MCP, memory, learning, telemetry, or persistent config changes without explicit approval.
