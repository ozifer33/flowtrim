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

FlowTrim includes four benchmark profiles:

- `synthetic-heavy`: public-safe fixtures covering command output, long context, exact evidence, code-generation pressure, and adversarial checks.
- `aql-vault-readonly`: read-only Aql Atlas decision fixtures. The expected default verdict is `hybrid-only`, because Atlas packet, `llm_brief`, source summaries, and generated indexes remain the semantic vault context economy.
- `work-code-readonly`: read-only code-lens analysis for private Work repos. Reports use anonymous repo/file labels plus hashes and aggregate metrics only; raw code, repo names, and local paths must not appear in JSON.
  It selects high-signal files for stress testing, so aggregate delete-list and LOC-delta numbers are not average prevalence estimates.
- `work-commit-history-readonly`: read-only private Work commit-history analysis. It uses anonymous repo/commit/file aliases and aggregate churn only; repo names, commit messages, file paths, raw diffs, and source bodies must not appear in reports.

FlowTrim's first native challenger is `flowtrim-native-command`, a clean-room
command-output packetizer. RTK remains an optional baseline/backend: FlowTrim may
select RTK when it wins safely, but native command output can become selected
when it preserves required facts and beats both raw and RTK in the measured case.

The Work profile defaults to a `9 x 12` high-signal sample: nine repositories and
twelve code files per repository. Use smaller limits only for quick local smoke
checks.

Run:

```bash
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile synthetic-heavy --format json
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile aql-vault-readonly --format json --aql-root <AQL_ATLAS_ROOT>
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile work-code-readonly --format json --work-root <WORK_ROOT> --repo-limit 9 --files-per-repo 12
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile work-commit-history-readonly --format json --work-repo <WORK_REPO_A> --work-repo <WORK_REPO_B>
```

Allowed claims are lane-specific: FlowTrim may say it selected a safe lower-token method for a measured lane, or that it correctly chose raw when compression was unsafe, slower, or not cheaper. It must not claim that it globally beats RTK, Ponytail, or Headroom. Headroom is reported as skipped when unavailable, not as a loss. Ponytail-style results are complexity-reduction evidence, not direct token compression unless generated text size is measured separately.

## Proof Test Matrix

The acceptance suite in `tests/test_proof_matrix.py` locks the proof plan:

- noisy command output may count as a token win only when required facts survive,
- exact evidence, failing traces, line diffs, and unsafe marker-only context must
  select raw or `insufficient-evidence`,
- Headroom unavailable is a skipped neutral method,
- Ponytail-style results are code-complexity evidence, not token savings,
- Aql vault semantic cases defer to Atlas context economy and keep the verdict
  `hybrid-only`,
- Work reports stay anonymous and aggregate-only.

Before publishing any public comparison, add a public/open-source readonly corpus;
private Work measurements are local evidence only.

The private commit-history profile can support only local/private claim language:
"private local evidence from historical Work commits" and "generated/lock-heavy
commits are separated as controls." It cannot support public or global benchmark
claims.

For a detailed, public-safe explanation of the latest proof run, including what
each profile tests, acceptance gates, result totals, and claim boundaries, see
`docs/benchmark-results.md`.

Run the proof matrix directly:

```bash
PYTHONPATH=src python3 -m unittest tests.test_proof_matrix
```

## Local Verification

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
uv run --no-project --with PyYAML python <SKILL_CREATOR_QUICK_VALIDATE> skills/flowtrim
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_orchestrator.py "npm test produced a long build log"
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py "abcd"
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile synthetic-heavy --format json
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile aql-vault-readonly --format json --aql-root <AQL_ATLAS_ROOT>
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile work-code-readonly --format json --work-root <WORK_ROOT> --repo-limit 9 --files-per-repo 12
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py suite --profile work-commit-history-readonly --format json --work-repo <WORK_REPO_A> --work-repo <WORK_REPO_B>
PYTHONPATH=src python3 - <<'PY'
from pathlib import Path
from flowtrim.privacy import scan_text
bad = []
for path in Path('.').rglob('*'):
    if (
        path.is_file()
        and '.git' not in path.parts
        and '__pycache__' not in path.parts
        and path.suffix != '.pyc'
        and not ('benchmarks' in path.parts and 'reports' in path.parts)
    ):
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
