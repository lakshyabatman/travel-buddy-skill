#!/usr/bin/env bash
# Copy this skill into an agent's skills folder, or add an AGENTS.md pointer to another repo.
# Never books, pays, or transfers points. Only copies files onto this machine.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILL_NAME="flight-points-optimiser"
# Files the running skill needs. SKILL.md is the source of truth.
ITEMS=(SKILL.md search.py history.py watch.py awards.py requirements.txt cards fees awards prompts)

usage() {
  cat <<USAGE
Install $SKILL_NAME from:
  $ROOT

Usage:
  $(basename "$0") --claude-code [--force]
  $(basename "$0") --cursor [--force]
  $(basename "$0") --project [--project-dir DIR] [--force]
  $(basename "$0") --agents --project-dir DIR [--force]
  $(basename "$0") --prompt
  $(basename "$0") --help

  --claude-code    Copy to ~/.claude/skills/$SKILL_NAME
  --cursor         Copy to ~/.cursor/skills/$SKILL_NAME
  --project        Copy to DIR/.claude/skills/$SKILL_NAME and DIR/.cursor/skills/$SKILL_NAME
                   (DIR defaults to the current working directory)
  --agents         Copy the skill into DIR/.claude/skills/ and add a relative pointer to DIR/AGENTS.md
  --prompt         Print the path of the paste-into-any-LLM prompt
  --force          Overwrite an existing install without asking
USAGE
}

copy_skill() {
  local dest="$1"
  if [[ -e "$dest" && "${FORCE:-0}" != 1 ]]; then
    echo "Destination already exists: $dest"
    echo "Re-run with --force to overwrite, or remove it first."
    exit 1
  fi
  mkdir -p "$dest"
  for item in "${ITEMS[@]}"; do
    if [[ -e "$ROOT/$item" ]]; then
      rm -rf "$dest/$item"
      cp -R "$ROOT/$item" "$dest/$item"
    fi
  done
  echo "Installed $SKILL_NAME to $dest"
}

append_agents() {
  local dir="$1"
  local file="$dir/AGENTS.md"
  # Prefer a project-local copy (portable). Fall back to this clone's absolute path.
  local skill_ref cards_ref
  if [[ -f "$dir/.claude/skills/$SKILL_NAME/SKILL.md" ]]; then
    skill_ref=".claude/skills/flight-points-optimiser/SKILL.md"
    cards_ref=".claude/skills/flight-points-optimiser/cards/<country>.yaml"
  else
    skill_ref="$ROOT/SKILL.md"
    cards_ref="$ROOT/cards/<country>.yaml"
  fi
  local block
  block=$(cat <<BLOCK

# Flight Points Optimiser
When the user wants the cheapest flight, a cash-vs-points comparison, flexible-date or
nearby-airport alternatives, or a price-watch on a route, read and follow
${skill_ref} (source of truth). Load ${cards_ref} when one exists.
Ask how flexible the dates are, and rank by the true total (base fare plus the bag, seat,
and other fees the traveller would pay). Ask each traveller's passport; there is no default
nationality. Never book, pay, or transfer points without explicit go-ahead. Never invent
fares, fees, ratios, or visa rules.
BLOCK
)
  mkdir -p "$dir"
  if [[ -f "$file" ]] && grep -q "Flight Points Optimiser" "$file"; then
    echo "AGENTS.md in $dir already mentions Flight Points Optimiser; left unchanged."
    return
  fi
  if [[ -f "$file" ]]; then
    printf '%s\n' "$block" >> "$file"
    echo "Appended a Flight Points Optimiser pointer to $file"
  else
    printf '%s\n' "# AGENTS" "$block" > "$file"
    echo "Created $file"
  fi
}

FORCE=0
MODE=""
PROJECT_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --claude-code|--cursor|--project|--agents|--prompt|--help|-h) MODE="$1"; shift ;;
    --project-dir) PROJECT_DIR="${2:-}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

case "$MODE" in
  --help|-h|"") usage ;;
  --prompt) echo "$ROOT/prompts/any-llm.md" ;;
  --claude-code) copy_skill "$HOME/.claude/skills/$SKILL_NAME" ;;
  --cursor) copy_skill "$HOME/.cursor/skills/$SKILL_NAME" ;;
  --project)
    dir="${PROJECT_DIR:-$PWD}"
    copy_skill "$dir/.claude/skills/$SKILL_NAME"
    copy_skill "$dir/.cursor/skills/$SKILL_NAME"
    append_agents "$dir"
    ;;
  --agents)
    if [[ -z "${PROJECT_DIR:-}" ]]; then
      echo "--agents requires --project-dir DIR" >&2
      exit 2
    fi
    # Copy the skill into the project first so AGENTS.md can use a portable relative path.
    copy_skill "$PROJECT_DIR/.claude/skills/$SKILL_NAME"
    append_agents "$PROJECT_DIR"
    ;;
  *) usage; exit 2 ;;
esac
