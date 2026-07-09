# FlowTrim Proof And Release Commands

Daily trim/run commands live in `SKILL.md`. The commands below are for
benchmark proofs, public-corpus experiments, and release gates.

## Benchmark Proofs

- Estimate fixture tokens: `flowtrim-benchmark "text"`
- Run synthetic proof: `flowtrim-benchmark suite --profile synthetic-heavy --format json`
- Run public playground proof: `flowtrim-benchmark suite --profile public-playground-readonly --format json`
- Audit pinned public manifest: `flowtrim-benchmark public-corpus audit --manifest benchmarks/public-corpus/manifest.v1.json --format json`
- Prepare pinned public corpus: `flowtrim-benchmark public-corpus prepare --manifest benchmarks/public-corpus/manifest.v1.json --cache-root /tmp/flowtrim-public-corpus`
- Run pinned public proof: `flowtrim-benchmark suite --profile public-open-source-readonly --public-corpus-manifest benchmarks/public-corpus/manifest.v1.json --public-cache-root /tmp/flowtrim-public-corpus --format json`
- Run private dogfood proof: `flowtrim-benchmark suite --profile work-dogfood-readonly --work-repo <WORK_REPO> --work-group <TICKET_OR_GROUP> --format json`
- Compare Headroom proof: `flowtrim-benchmark compare --baseline-report /tmp/flowtrim-public-baseline.json --candidate-report /tmp/flowtrim-public-headroom.json --focus headroom-direct --format markdown`

## Release Gates

- Check a public claim: `flowtrim-benchmark claim-check --report /tmp/flowtrim-public-baseline.json --claim "On the pinned public corpus, FlowTrim selected a safe lower-token method for measured lanes." --format json`
- Run privacy gate: `flowtrim-benchmark privacy-scan --tracked --path /tmp/flowtrim-public-baseline.json --format json`
- Run docs gate: `flowtrim-benchmark docs-check --format json`
- Run release gate: `flowtrim-benchmark release-check --report /tmp/flowtrim-public-baseline.json --unit-tests-passed --skill-validation-passed --benchmark-smoke-passed --privacy-scan-passed --sanitized-report-present --package-entrypoint-ready --license-reviewed --tool-versions-captured --format markdown`

## Source-Checkout Fallback

Before installing the package:

- `PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_benchmark.py "text"`
- `PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_trim.py --file /tmp/build.log`
- `PYTHONPATH=src python3 skills/flowtrim/scripts/flowtrim_run.py -- npm test`
