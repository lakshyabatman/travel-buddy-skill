# Claude Code adapter

`SKILL.md` at the **repository root** is the source of truth. This folder exists so that, after
you clone the repo into a project (or run the install script), Claude Code can discover the skill.

## Use it in this repo (project skill)

From the repository root:

```bash
./scripts/install.sh --project
```

That copies `SKILL.md`, `cards/` and `search.py` into this directory so Claude Code picks them
up as a project skill. Re-run after you pull updates. Do not edit the copy; edit the root
`SKILL.md` and re-install.

## Use it in every project (user skill)

```bash
./scripts/install.sh --claude-code
```

This installs a copy into `~/.claude/skills/flight-points-optimiser/`.
