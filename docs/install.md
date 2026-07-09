# FlowTrim Install Guide

Official install path: Codex.

FlowTrim has two parts:

- a Python CLI: `flowtrim-run`, `flowtrim-trim`, `flowtrim-classify`, and
  `flowtrim-benchmark`
- a Codex skill folder: `skills/flowtrim`

Use `flowtrim-run` and `flowtrim-trim` for day-to-day token reduction, the
benchmark CLI for proof gates, and the skill when you want Codex to apply the
FlowTrim lane policy while working.

## Official Codex Install

User-level Codex install:

```bash
git clone https://github.com/ozifer33/flowtrim.git
cd flowtrim
python3 -m pip install .
node scripts/flowtrim-skill-install.mjs --agent codex --scope user
flowtrim-benchmark doctor --format json
```

Project-local Codex install:

```bash
git clone https://github.com/ozifer33/flowtrim.git
cd flowtrim
python3 -m pip install .
node scripts/flowtrim-skill-install.mjs --agent codex --scope project --project /path/to/project
```

Expected: `doctor` returns `valid: true`.

## Manual Codex Fallback

If Node is unavailable, copy the skill folder manually:

```bash
mkdir -p "$HOME/.agents/skills"
cp -R /path/to/flowtrim/skills/flowtrim "$HOME/.agents/skills/flowtrim"
```

Project-local fallback:

```bash
mkdir -p .agents/skills
cp -R /path/to/flowtrim/skills/flowtrim .agents/skills/flowtrim
```

Minimum installed files:

- `SKILL.md`
- `references/lane-policy.md`
- `references/benchmark-gates.md`
- `references/safety-rules.md`
- `scripts/flowtrim_benchmark.py`
- `scripts/flowtrim_orchestrator.py`
- `agents/openai.yaml`

## Not The Official Path

`npx is not the official install path` for FlowTrim yet. It remains an optional
experiment because the current local proof found that older `npx`/npm versions
can timeout or fail on `github:ozifer33/flowtrim`.

These commands are compatibility experiments only:

```bash
npx github:ozifer33/flowtrim --agent codex --scope user
npx github:ozifer33/flowtrim --agent claude --scope user
npx github:ozifer33/flowtrim --agent copilot --scope project --project .
```

Do not claim them as verified until `flowtrim-benchmark install-check --run-npx`
passes in the target environment.

## Optional compatibility notes

FlowTrim keeps metadata for future agent support, but Codex is the only official
install path in this public alpha.

| Tool | Project path | User path | Status |
| --- | --- | --- | --- |
| Codex | `.agents/skills/` | `~/.agents/skills/` | official install path |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` | needs verification |
| GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` | needs verification |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` | needs verification |
| Gemini CLI | `.gemini/skills/` | `~/.gemini/skills/` | needs verification |
| Antigravity | `.agent/skills/` | `~/.gemini/antigravity/skills/` | needs verification |
| OpenCode | `.opencode/skills/` | `~/.config/opencode/skills/` | needs verification |
| Windsurf | `.windsurf/skills/` | `~/.codeium/windsurf/skills/` | needs verification |

For tools marked `needs verification`, copy `skills/flowtrim` only after
checking that the host supports `SKILL.md` folders in that location.

## Smoke Check

After installing the CLI:

```bash
flowtrim-benchmark abcd
flowtrim-classify "npm test produced a long build log"
flowtrim-benchmark doctor --format json
flowtrim-benchmark install-check --format json
```

Expected:

- `flowtrim-benchmark abcd` prints `1`
- classifier prints `command-output`
- doctor reports `valid: true`
- install-check reports `flowtrim-install-check/v1`

See `docs/install-verification.md` for what is automated, skipped-neutral, or
still manual.
