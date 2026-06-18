# Lane Policy

| Lane | Use when | Default |
|---|---|---|
| `exact-evidence` | Failing detail, diffs, security output, source quotes, short commands | Raw |
| `repo-context` | Agent needs project orientation | Read repo rules, README, scripts |
| `command-output` | Test/build/search/file output is noisy | Compare raw with measured reduction |
| `code-generation` | Agent is about to add code | Prefer existing code, stdlib, installed deps, and smaller diffs |
| `long-context` | JSON, traces, logs, or handoff are long | Direct compression only if facts remain auditable |

Never compare lanes with a single universal score. Each lane has its own primary metric and guard metrics.
