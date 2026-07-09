# FlowTrim Quickstart

FlowTrim is a public alpha candidate for checking when an AI agent should keep
raw evidence and when it can use a smaller, audited context packet.

## Install

From a checkout:

```bash
python3 -m pip install -e .
```

Smoke check:

```bash
flowtrim-benchmark abcd
flowtrim-classify "npm test produced a long build log"
```

Expected output:

- `flowtrim-benchmark abcd` prints `1`.
- `flowtrim-classify ...` prints `command-output`.

## Trim Real Output

Run a command with trimmed output (exit code is preserved):

```bash
flowtrim-run -- python3 -m pytest -q
```

Or reduce a noisy log you already captured while keeping required facts, with
raw fallback when any gate fails:

```bash
flowtrim-trim --file benchmarks/fixtures/logs/noisy-build-fail.txt --must-preserve "src/worker.py::test_retry_policy"
```

The packet goes to stdout; a stats line such as
`flowtrim-trim: trimmed 155 -> 63 tokens (59.4% saved)` goes to stderr. Add
`--format json` to capture the full decision as evidence, or
`--fallback excerpt` to keep a bounded head/tail/error excerpt when the packet
gates fail.

## Run Public-Safe Proofs

These commands require no private repositories and no network clone:

```bash
flowtrim-benchmark suite --profile synthetic-heavy --format json
flowtrim-benchmark suite --profile public-playground-readonly --format json
flowtrim-benchmark public-corpus audit --manifest benchmarks/public-corpus/manifest.v1.json --format json
```

## Run Gates

```bash
flowtrim-benchmark privacy-scan --tracked --format json
flowtrim-benchmark docs-check --format json
flowtrim-benchmark skill-check --skill-root skills/flowtrim --format json
flowtrim-benchmark doctor --format json
```

`doctor` is the one-command public alpha health check. It summarizes package
metadata, CLI smoke behavior, docs, skill shape, privacy scan, public corpus
manifest audit, and public playground proof without printing local paths.

Claims should be checked against a generated report:

```bash
flowtrim-benchmark suite --profile synthetic-heavy --format json > /tmp/flowtrim-synthetic.json
flowtrim-benchmark claim-check --report /tmp/flowtrim-synthetic.json --claim "FlowTrim selected a safe lower-token method for this measured lane." --format json
```

## Pinned Public Corpus

The pinned public corpus is manual because it may clone large public repos into a
local cache:

```bash
flowtrim-benchmark public-corpus prepare --manifest benchmarks/public-corpus/manifest.v1.json --cache-root /tmp/flowtrim-public-corpus
flowtrim-benchmark suite --profile public-open-source-readonly --public-corpus-manifest benchmarks/public-corpus/manifest.v1.json --public-cache-root /tmp/flowtrim-public-corpus --format json
```

This supports only pinned-corpus claims, not global benchmark claims.

## Source-Checkout Fallback

Use this only before installing the package:

```bash
PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py abcd
```
