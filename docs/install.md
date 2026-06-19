# FlowTrim Install Guide

FlowTrim has two parts:

- a Python CLI: `flowtrim-benchmark` and `flowtrim-classify`
- an agent skill folder: `skills/flowtrim`

Install the CLI when you want to run benchmark gates. Install the skill when you
want an agent to use the FlowTrim lane policy while working.

## Python CLI

```bash
git clone https://github.com/ozifer33/flowtrim.git
cd flowtrim
python3 -m pip install .
flowtrim-benchmark doctor --format json
```

Expected: `doctor` returns `valid: true`.

## Claude Code

Claude Code can install FlowTrim as a plugin marketplace:

```text
/plugin marketplace add ozifer33/flowtrim
/plugin install flowtrim@flowtrim
```

Plugin invocation is namespaced:

```text
/flowtrim:flowtrim
```

Manual project install:

```bash
mkdir -p .claude/skills
cp -R /path/to/flowtrim/skills/flowtrim .claude/skills/flowtrim
```

Manual user install:

```bash
mkdir -p "$HOME/.claude/skills"
cp -R /path/to/flowtrim/skills/flowtrim "$HOME/.claude/skills/flowtrim"
```

## Codex

The `npx` path is a convenience installer, not a universal requirement. Use it
only when Node is available:

```bash
npx github:ozifer33/flowtrim --agent codex --scope user
```

Manual user install:

```bash
mkdir -p "$HOME/.agents/skills"
cp -R /path/to/flowtrim/skills/flowtrim "$HOME/.agents/skills/flowtrim"
```

Manual project install:

```bash
mkdir -p .agents/skills
cp -R /path/to/flowtrim/skills/flowtrim .agents/skills/flowtrim
```

## GitHub Copilot

Copilot can use repository skills and repository instructions. Prefer a project
install for teams:

```bash
npx github:ozifer33/flowtrim --agent copilot --scope project --project .
```

Manual project install:

```bash
mkdir -p .github/skills
cp -R /path/to/flowtrim/skills/flowtrim .github/skills/flowtrim
cp /path/to/flowtrim/.github/copilot-instructions.md .github/copilot-instructions.md
```

If your `gh` version supports skill installation, inspect before installing:

```bash
gh skill preview ozifer33/flowtrim flowtrim
gh skill install ozifer33/flowtrim flowtrim
```

## Convenience Installer

The Node installer supports only verified first-class targets:

```bash
npx github:ozifer33/flowtrim --agent claude --scope user
npx github:ozifer33/flowtrim --agent codex --scope user
npx github:ozifer33/flowtrim --agent copilot --scope project --project .
```

Options:

- `--agent claude|codex|copilot`
- `--scope user|project`
- `--project <path>`
- `--dry-run`
- `--force`

It copies only the FlowTrim skill allowlist: `SKILL.md`, `references/`,
`scripts/`, and `agents/`. It refuses to overwrite an existing install unless
`--force` is present.

## Manual Path Matrix

| Tool | Project path | User path | Status |
| --- | --- | --- | --- |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` | verified install path |
| Codex | `.agents/skills/` | `~/.agents/skills/` | verified install path |
| GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` | verified install path |
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
```

Expected:

- `flowtrim-benchmark abcd` prints `1`
- classifier prints `command-output`
- doctor reports `valid: true`
