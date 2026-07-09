# Changelog

## Unreleased

- Added the `flowtrim-trim` CLI: a fail-safe reducer that turns noisy command
  output into a compact fact packet when preservation and token gates pass, and
  returns raw output unchanged otherwise.
- Added the `flowtrim-run` CLI: runs a command, uses its exit code as the
  pass/fail ground truth, trims passing output, keeps a bounded error excerpt
  for failing output, and propagates the exit code.
- Taught the command-output extractor real log shapes (pytest, Jest/Vitest,
  Go, Cargo, tsc, npm), multi-line error capture, template-based noise
  detection, and URL/date junk filtering for file paths.
- Unified the measured benchmark packet with the shipped CLI packet, so
  scoreboard token savings now describe real `flowtrim-trim` output.
- Added a dedicated long-context reducer that keeps trace/source/job ids,
  paths, and error labels auditable, plus an opt-in `--fallback excerpt` mode
  with omission markers.
- Made the lane classifier word-boundary aware, stopped routing every mention
  of "failed" to exact-evidence, and added Thai task keywords.
- Counted non-ASCII (Thai/CJK) text per character in token estimates and added
  an optional `flowtrim[tokens]` extra with `FLOWTRIM_TOKENIZER=tiktoken`.
- Slimmed the skill command list into `references/commands.md` and removed the
  unused parallel-runner module.

## 0.1.0-public-alpha

- Added installable CLI entrypoints for benchmark and lane classification.
- Added public-safe synthetic, playground, and pinned public-corpus proof paths.
- Added privacy, claim, release, skill-shape, docs, and public-corpus audit gates.
- Added optional Headroom direct comparison support without enabling wrap, proxy,
  MCP, memory, learning, or config writes.
- Kept private Work evidence local, anonymous, and excluded from public claims.
