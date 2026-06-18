# FlowTrim

FlowTrim is a private-first, public-ready Codex skill and Python benchmark harness for reducing AI agent token usage in work repositories without changing task results.

FlowTrim routes each flow through the smallest safe context path:

- use command-output reduction for noisy shell output,
- use code-simplification pressure before generating unnecessary code,
- use direct long-context compression only when facts remain auditable,
- keep raw output for exact evidence, failures, short commands, and sensitive data.

## Status

FlowTrim starts as a local proof of concept. It should not be published, installed globally, or used on private Work repositories until its fixture tests, privacy scan, and sanitized benchmark gates pass.

## Safety Rules

- No RTK hooks, Headroom proxy/wrap, MCP registration, memory, or shell config changes by default.
- No private logs, secrets, production traces, customer data, `.env` values, or Work repo names in this repo.
- No token-saving claim counts unless preservation and wall-time gates pass.
