# Audit: install and usability

Date: 2026-11-25 (Asia/Calcutta). Scope: a from-scratch walk-through of every advertised
install path, plus the docs site and README instructions. No files were installed into the
auditor's real home directory; a temporary `HOME` and temporary project dirs were used.

## Walk-through

| Path | Result |
|---|---|
| `./scripts/install.sh --help` | Prints the commands below. After a wording fix, `--agents` help matches behaviour. |
| `./scripts/install.sh --claude-code` | Copies `SKILL.md`, `cards/`, `search.py`, `prompts/`, `requirements.txt` to `~/.claude/skills/flight-points-optimiser/`. |
| `./scripts/install.sh --cursor` | Same payload to `~/.cursor/skills/flight-points-optimiser/`. |
| `./scripts/install.sh --project --project-dir DIR` | Copies into `DIR/.claude/skills/` and `DIR/.cursor/skills/`. |
| `./scripts/install.sh --agents --project-dir DIR` | Installs a project copy and writes `DIR/AGENTS.md`. |
| `./scripts/install.sh --prompt` | Prints `prompts/any-llm.md`. |
| Re-run without `--force` | Exits 1 with a clear message; does not overwrite. |
| Working inside this repo | Root `AGENTS.md` and `.cursor/rules/flight-points-optimiser.mdc` already point at `SKILL.md`. No install required. |
| Docs site `docs/index.html` | Static, no build step to *view*. Coverage table is already in the file; `scripts/build_docs.py` refreshes it. |

## Issues and fixes

1. **Copied `.venv` was broken.** `cp -a` of the old repo brought a virtualenv whose paths still
   pointed at `/workspace/india-flight-optimiser`. `pip` then installed packages into the *old*
   venv. **Fix:** deleted the new repo's `.venv` and created a fresh one. Uninstalled the extra
   packages (`jsonschema` and its deps) from the old venv. Project files in
   `india-flight-optimiser/` were not edited. `.gitignore` already excludes `.venv/`.
2. **`--agents` wrote an absolute path** to `/workspace/flight-points-optimiser/SKILL.md`. That
   breaks if the clone is moved, and it did not copy the skill into the other repo. **Fix:**
   `--agents` now copies the skill into `DIR/.claude/skills/` and writes a *relative* pointer
   into `DIR/AGENTS.md`. `--project` also appends that pointer. README and the docs site were
   updated to describe this.
3. **Adapter folders could have drifted** if they contained a second full copy of `SKILL.md`.
   **Fix:** `.claude/skills/…` and `.cursor/skills/…` in this repo hold only READMEs that point
   at the root `SKILL.md` and the install script. Copied payloads from `--project` run inside
   this repo are gitignored.
4. **PyYAML turned `last_checked: 2026-11-25` into `datetime.date`**, so the first schema
   validation run reported 62 false errors. **Fix:** `validate_cards.py` loads YAML with a
   loader that keeps ISO dates as strings. Validation now reports 0 errors.

## Remaining nits (not fixed)

- Claude Code and Cursor user-level skills still need the human to restart or refresh the
  app after install; we cannot test that here.
- The README and docs clone URL now point at
  `https://github.com/lakshyabatman/travel-buddy-skill` (filled in when the repo was published).
  The skill directory name remains `flight-points-optimiser`. The Pages site is
  `https://lakshyabatman.github.io/travel-buddy-skill/`.
- `--project` inside this repo would copy payloads next to the adapter READMEs; they are
  gitignored, but contributors should prefer the root files.

## Verdict

Each advertised install path works after the fixes above. A new user can follow the README
or `docs/index.html` without a site-generator or a paid API.
