# Safety Rules

Keep raw output for:

- failing test details,
- security findings,
- source quotes,
- line-level diffs,
- short commands,
- private data,
- any artifact that must be auditable exactly.

Do not enable hooks, proxy, MCP, memory, learning, telemetry, or persistent config edits without explicit approval.

Do not write private Work repo logs, secrets, `.env` values, production traces, customer data, or local private paths into public fixtures.
