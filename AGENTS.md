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

Date flexibility is an explicit question, never a silent default. Before searching, ask whether
the dates are flexible and by how much: fixed, ±1 day, ±3 days, ±1 week, any time in a given
month, or weekends only. On a round trip, ask about the return separately. Search exact dates
only if the user says fixed. If you cannot ask (for example an automated run), use ±3 days and
say so. Scan that window (`search.py --flex N`, the Google Flights date grid or price graph,
Skyscanner's month view) and sample it when it is wide. After the ranked table, always include
an Alternative dates table: the top 3–5 cheaper depart/return pairs, with the saving in money
and percent, airline and stops, and the trade-off (weekday, red-eye, longer trip), or say
plainly that none were cheaper. If award space was checked, note when a nearby date is better.

Supporting files: `cards/`, `search.py`, `prompts/any-llm.md`.
