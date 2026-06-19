# FlowTrim Install Verification

Schema: `flowtrim-install-check/v1`.

`install-check` verifies the public install paths without writing into real user
skill directories by default. It writes only to a temporary root, reports
aggregate evidence, and treats unavailable external agent CLIs as
`skipped-neutral`.

```bash
flowtrim-benchmark install-check --format json
```

Optional external checks:

```bash
flowtrim-benchmark install-check --run-npx --format json
flowtrim-benchmark install-check --run-gh-skill --format json
flowtrim-benchmark install-check --run-claude-plugin --format json
flowtrim-benchmark install-check --clean-clone-url https://github.com/ozifer33/flowtrim.git --format json
```

| Method | Automated | Required tool | Default status | Claim allowed |
| --- | --- | --- | --- | --- |
| Python CLI package smoke | yes | Python | covered by `doctor` | CLI package checks pass locally |
| Skill source shape | yes | none | passed | skill allowlist present |
| Node project installer | yes | Node | passed when Node exists | project install layout verified |
| Shell installer | yes | sh and Node | passed when Node exists | project install layout verified |
| PowerShell installer | yes | pwsh | skipped-neutral if missing | not verified until pwsh run passes |
| Clean GitHub clone | optional | git, Python, network | skipped-neutral | not verified until requested run passes |
| `npx github:ozifer33/flowtrim` | optional | npx, network | skipped-neutral | not verified until requested run passes |
| GitHub Copilot skill | optional | `gh skill` | skipped-neutral | not verified until preview/install proof exists |
| Claude Code plugin | manual/optional | Claude Code | skipped-neutral | not verified until manual plugin install proof exists |

## Latest Local Evidence

Local proof date: June 19, 2026.

Passed:

- Codex skill source shape.
- Node project install into `.agents/skills/flowtrim`.
- Shell installer project install into `.agents/skills/flowtrim`.
- Clean GitHub clone plus `python3 -m pip install .` and CLI smoke.

Skipped-neutral:

- PowerShell installer because `pwsh` was unavailable.
- GitHub Copilot `gh skill` because `gh` was unavailable.
- Claude Code plugin install because it still needs manual Claude Code UI proof.

Not official:

- `npx github:ozifer33/flowtrim` was requested in this local environment and did
  not pass. Keep it as an optional experiment until a requested `--run-npx`
  proof passes in the target environment.

Manual Claude Code plugin proof:

```text
/plugin marketplace add ozifer33/flowtrim
/plugin install flowtrim@flowtrim
/flowtrim:flowtrim
```

Expected: the FlowTrim skill is discoverable and can answer lane-policy
questions without enabling private data collection.

Manual GitHub Copilot skill proof:

```bash
gh skill preview ozifer33/flowtrim flowtrim
gh skill install ozifer33/flowtrim flowtrim --scope user
```

Expected: preview/install succeeds. If `gh skill` is unavailable, record
`skipped-neutral`, not a failure.

Tools marked `needs verification` in `docs/install.md` remain not verified until
one real install proof exists per tool. Do not claim verified support for
Cursor, Gemini CLI, Antigravity, OpenCode, or Windsurf from this repo alone.
