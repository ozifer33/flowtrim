# Benchmark Gates

Token saving counts only when:

- Result preservation passes.
- Requirement preservation passes.
- Selected method beats raw and does not lose to the lane winner.
- Wall-time overhead is within the lane budget.
- Parallel lanes are read-only or isolated.
- Compressed output remains auditable.

Report `insufficient-evidence` instead of claiming a win when a primary or guard metric is missing.
