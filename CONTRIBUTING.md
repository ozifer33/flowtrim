# Contributing

FlowTrim accepts changes that improve public usefulness without weakening
privacy, preservation, or claim boundaries.

## Development Setup

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests
```

Run public-safe smoke checks:

```bash
flowtrim-benchmark suite --profile synthetic-heavy --format json
flowtrim-benchmark suite --profile public-playground-readonly --format json
flowtrim-benchmark privacy-scan --tracked --format json
flowtrim-benchmark docs-check --format json
flowtrim-benchmark skill-check --skill-root skills/flowtrim --format json
```

## Privacy Rules

- Do not commit private logs, source snippets, raw diffs, local machine paths, or
  repo names from private work.
- Public reports must stay aggregate-only or alias-only.
- Generated benchmark reports are local evidence until manually reviewed.

## Claim Rules

Allowed claims are lane-specific and report-specific, such as:

- FlowTrim selected a safe lower-token method on a measured public-safe lane.
- FlowTrim correctly selected raw for exact evidence.
- Code-lens cases reduced complexity without claiming direct token savings.

Forbidden claims include:

- Global wins over RTK, Ponytail, or Headroom.
- Public claims based on private evidence.
- Headroom losses when Headroom was skipped or unavailable.

## Public Corpus

The public corpus manifest must use public HTTPS GitHub URLs, pinned commit
SHAs, declared licenses, and language-family metadata. The benchmark suite must
run read-only against a prepared cache and must not clone during the read-only
suite.

## Source-Checkout Fallback

Only use source-path commands before package install:

```bash
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py abcd
```
