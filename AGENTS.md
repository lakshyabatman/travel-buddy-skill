# AGENTS

This repository is the **Flight Points Optimiser** skill. `SKILL.md` is the source of truth.
Read it for the cheapest flight, a cash-versus-points comparison, flexible dates, or a price
watch. There is no default country or passport. `cards/india.yaml` is one issuing country, not
a default route.

## Quick mode first

For a simple ask ("cheap flight to X"), follow **Quick mode** in `SKILL.md` and stop there
unless they want a deep dive:

- Ask only for missing dates and flexibility, passengers, and cards if they want points.
- Exact dates only if they say fixed. If you cannot ask, use ±3 days and say so.
- At most about 5 searches. Cash top 3 with a true total and a visa flag (check, if you did
  not ask for a passport).
- One line on whether points look plausible. Never claim a seat is free.
- Never book, pay, or transfer.

`search.py`, `history.py`, and `watch.py` are an optional scraper. The skill works in a
browser or with a built-in flight search if they are missing or broken.

## Full mode

When they ask for the deep dive, follow the rest of `SKILL.md`: fee lines, official visa
sources, award links from `awards/links.yaml` plus a 30-second self-check, an Alternative
dates table, and a buy-or-wait note that does not invent history. Do not invent fares, fees,
ratios, or visa rules.

Supporting files: `cards/`, `fees/`, `awards/links.yaml`, `prompts/any-llm.md`.
