# Cursor adapter (skills)

`SKILL.md` at the **repository root** is the source of truth.

```bash
# Project skill (this repo, or another project directory)
./scripts/install.sh --project

# User-level Cursor skill
./scripts/install.sh --cursor
```

`--project` copies `SKILL.md`, `cards/` and `search.py` into `.cursor/skills/flight-points-optimiser/`
of the target project. `--cursor` copies them to `~/.cursor/skills/flight-points-optimiser/`.
A Cursor rule that points at the root `SKILL.md` also lives at `.cursor/rules/flight-points-optimiser.mdc`.
