# FlowTrim Instructions For GitHub Copilot

Use FlowTrim as a context-economy guardrail when work may produce long command
output, large code searches, generated code, JSON/tool traces, or handoff
context.

Preserve the user objective, requirements, paths, commands, URLs, and evidence
boundaries before reducing context. Use raw output for exact quotes, line-level
diffs, failing stack traces, security evidence, validation failures, secrets, or
explicit exact-output requests.

Prefer the smallest safe lane:

- `command-output`: summarize noisy test/build logs only when required paths,
  failing IDs, error labels, feature flags, and pass/fail facts remain.
- `code-generation`: remove avoidable helper abstractions and duplicate
  conversion logic before adding code.
- `long-context`: compress only when trace IDs, job IDs, source IDs,
  requirements, and retrieval paths remain auditable.
- `repo-context`: read local repo instructions, scripts, and verification
  commands before choosing an approach.

If the FlowTrim CLI is installed, use aggregate-only checks such as:

```bash
flowtrim-benchmark doctor --format json
flowtrim-benchmark suite --profile public-playground-readonly --format json
```

Do not store private logs, raw source excerpts, `.env` values, Work repo names,
secret-like values, raw diffs, or local home paths in generated reports.
