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
- Generated reports stay local in `benchmarks/reports/` unless a sanitized report is explicitly reviewed for publication.

## Benchmark Lab

FlowTrim includes two benchmark profiles:

- `synthetic-heavy`: public-safe fixtures covering command output, long context, exact evidence, code-generation pressure, and adversarial checks.
- `aql-vault-readonly`: read-only Aql Atlas decision fixtures. The expected default verdict is `hybrid-only`, because Atlas packet, `llm_brief`, source summaries, and generated indexes remain the semantic vault context economy.

Run:

```bash
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile synthetic-heavy --format json
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile aql-vault-readonly --format json --aql-root <AQL_ATLAS_ROOT>
```

Allowed claims are lane-specific: FlowTrim may say it selected a safe lower-token method for a measured lane, or that it correctly chose raw when compression was unsafe, slower, or not cheaper. It must not claim that it globally beats RTK, Ponytail, or Headroom. Headroom is reported as skipped when unavailable, not as a loss. Ponytail-style results are complexity-reduction evidence, not direct token compression unless generated text size is measured separately.

## Local Verification

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
uv run --no-project --with PyYAML python <SKILL_CREATOR_QUICK_VALIDATE> skills/flowtrim
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_orchestrator.py "npm test produced a long build log"
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py "abcd"
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile synthetic-heavy --format json
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile aql-vault-readonly --format json --aql-root <AQL_ATLAS_ROOT>
PYTHONPATH=src python3 - <<'PY'
from pathlib import Path
from flowtrim.privacy import scan_text
bad = []
for path in Path('.').rglob('*'):
    if path.is_file() and '.git' not in path.parts:
        findings = scan_text(path.read_text(errors='ignore'))
        if findings:
            bad.append((path.as_posix(), findings))
print(bad)
raise SystemExit(1 if bad else 0)
PY
```

Expected:

- all tests pass,
- skill validation passes,
- classifier prints `command-output`,
- benchmark prints `1`,
- benchmark suites print privacy-safe JSON,
- privacy scan prints `[]`.
