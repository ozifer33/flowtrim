# FlowTrim Public Alpha Benchmark

Aggregate-only scoreboard generated from sanitized FlowTrim reports.
It supports lane-specific evidence only, not a global benchmark claim.

| Profile | Cases | Token wins | Tokens saved | Raw refusals | Code-lens wins | Claim boundary |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| synthetic-heavy | 14 | 4 | 521 | 3 | 2 | Public-safe fixture evidence |
| public-playground-readonly | 12 | 8 | 2824 | 2 | 1 | Public-safe usability smoke |

## Reading The Numbers

- Token wins count only when a smaller method preserves required facts and stays within the wall-time budget.
- Raw refusals are good outcomes for exact evidence such as quotes, stack traces, and line-level diffs.
- Code-lens wins are complexity-reduction evidence, not direct token-saving claims.
- Headroom skipped or unavailable is neutral, not a loss.

No private Work repo names, paths, commit messages, source lines, or raw diffs are included.
