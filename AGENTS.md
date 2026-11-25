# AGENTS

This repository is the **Flight Points Optimiser** skill. `SKILL.md` at the repo root is the
source of truth. If you are an agent (Codex, Claude Code, Cursor, Copilot, Goose, or any other
tool that reads `AGENTS.md`), read `SKILL.md` and follow it whenever the user wants:

- the cheapest flight between two places (or "anywhere"),
- a comparison of cash fares vs transferable credit-card points or airline miles,
- flexible-date or nearby-airport alternatives,
- or a price-watch alert on a route.

Do not book, pay, or transfer points unless the user has given explicit go-ahead for that exact
action. Do not invent fares, award prices, or transfer ratios. Load `cards/<country>.yaml` when
one exists; otherwise research the issuer's official page and label figures unverified.

Supporting files: `cards/`, `search.py`, `prompts/any-llm.md`.
