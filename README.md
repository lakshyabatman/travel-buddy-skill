# Flight Points Optimiser

This repository is named **travel-buddy-skill**. The agent skill it publishes is
**flight-points-optimiser** (`SKILL.md`). Docs:
[https://lakshyabatman.github.io/travel-buddy-skill/](https://lakshyabatman.github.io/travel-buddy-skill/).

An Agent Skill that finds the cheapest way to fly **from anywhere**, paying **cash** or with
**transferable credit-card points and airline miles**, using **free sources only**: no paid
flight APIs.

It tells your AI agent how to:

- search cash fares (the agent's own flight search first, then Google Flights, Skyscanner,
  Kayak, the airline's site, or the bundled `search.py`);
- try flexible dates (±3 days, date grids), nearby and secondary airports, positioning hops to
  better-connected hubs, open-jaw tickets, rail-plus-air, and separate tickets via hubs, with
  self-transfer and visa risks stated;
- compare each card's transfer partners using `cards/<country>.yaml`: points needed, taxes,
  value per point, caps, fees, transfer times (and research the issuer live if that country or
  card has no file yet);
- return a ranked table with exact transfer and booking steps, plus alternatives;
- optionally set up a price-watch routine that alerts only on real drops.

It **never books, pays, or transfers points** without your explicit go-ahead, and it must cite a
source for every fare and ratio.

`SKILL.md` is the source of truth. Adapters for Claude Code, Cursor, Codex / `AGENTS.md` readers,
and a paste-in prompt for any LLM all point back at it.

v1 ships **India** card data only (`cards/india.yaml`: HDFC Infinia, HDFC Diners Club Black,
Axis Atlas, Amex India Membership Rewards). US, UK, UAE, Singapore, Canada and Australia files
are planned; see `CONTRIBUTING.md`.

## Install

Clone the repo, then use the script or the manual steps below.

```bash
git clone https://github.com/lakshyabatman/travel-buddy-skill
cd travel-buddy-skill
chmod +x scripts/install.sh
```

| Agent | Command | What it does |
|---|---|---|
| Claude Code | `./scripts/install.sh --claude-code` | Copies the skill into `~/.claude/skills/flight-points-optimiser/` |
| Cursor | `./scripts/install.sh --cursor` | Copies the skill into `~/.cursor/skills/flight-points-optimiser/` |
| This repo / a project | `./scripts/install.sh --project` | Copies into that project's `.claude/skills/` and `.cursor/skills/` |
| Codex and other `AGENTS.md` readers | Clone or add the repo; `AGENTS.md` already points at `SKILL.md` | No extra copy needed when you work inside this repo. To use it in another repo, run `./scripts/install.sh --agents --project-dir /path/to/other-repo` (copies the skill into that repo and adds a relative pointer to its `AGENTS.md`) |
| Any LLM (ChatGPT, Gemini, a web chat, …) | Open `prompts/any-llm.md`, paste it into the chat, and attach a card file if you have one | Works without a skills folder |

`./scripts/install.sh --help` lists the same options. You can also copy `SKILL.md`, `cards/` and
`search.py` into your agent's skills directory by hand.

Then ask, for example:

> Cheapest way to get from London to Tokyo around 10 March, ±3 days, economy, 2 adults, in GBP.
> I have an Amex UK Platinum and 180,000 Membership Rewards points.

Or, from India:

> Cheapest way to get from Bengaluru to Tokyo around 10 March. I have HDFC Infinia (180,000
> points) and Axis Atlas (40,000 EDGE Miles).

## search.py (optional)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python search.py LHR JFK 2026-12-16 --currency GBP
python search.py SFO NRT 2027-02-05 --flex 3 --airports SFO,OAK,SJC --currency USD --top 15
python search.py BLR SIN 2027-01-10 --return 2027-01-17 --cabin business --currency INR
python search.py LHR JFK 2027-03-01 --json-only > out.json
```

`--currency` is passed through to Google Flights (ISO 4217: `USD`, `GBP`, `EUR`, `INR`, `JPY`,
…). If you omit it, Google chooses. The script does not convert currencies itself.

It prints a price-sorted table and a "cheapest per origin/date" view, followed by JSON (use
`--json-only` for agents). Prices are totals for all passengers as shown by Google Flights at
fetch time.

Notes:
- `fast-flights` is an unofficial scraper. It was tested working on 2026-11-25 (v3.1.0) on both
  LHR–JFK and BLR–DEL, but it can break or be rate-limited at any time. If it fails, use Google
  Flights, Skyscanner or Kayak in a browser.
- Round-trip results are less complete than one-way searches, so cross-check round trips in a
  browser.
- `--delay` (default 1.5 s) spaces out requests. Keep `--flex` × `--airports` small.

## Docs site

A static GitHub Pages site lives in `docs/index.html` and is published at
https://lakshyabatman.github.io/travel-buddy-skill/ (no build step to view the file). After you
change card files, refresh the coverage table with `python scripts/build_docs.py`.

## Other data sources (optional)

- **Firecrawl Alexandria flights** (https://alexandria.firecrawl.dev/go/flights): **live flight
  status** (delays, cancellations, ground stops, security lines) for agents. It does **not**
  provide fares, and it needs a Firecrawl account or API key with Alexandria enabled. The skill
  mentions it only as an optional disruption check for a shortlisted flight or a tight
  self-transfer.

## Validate

```bash
pip install -r requirements.txt
python scripts/validate_cards.py
```

The script checks every `cards/*.yaml` against `schemas/cards.schema.json` and warns when
`last_checked` is more than 60 days old. GitHub Actions runs this plus a `search.py` smoke test
(see `.github/workflows/ci.yml`).

## Disclaimer

**Transfer ratios, partners, caps and fees change often, sometimes overnight and without notice.**
Card files record where and when each number was checked; entries marked `verified: false` come
from blogs, or from official pages that are old or behind a login. **Always confirm the ratio
in your bank's transfer portal, and confirm award seat availability on the airline programme's
site, before transferring.** Point transfers are almost always irreversible. This project is not
affiliated with any bank, airline or loyalty programme, and nothing here is financial advice.

## License

MIT, see [LICENSE](LICENSE). Copyright (c) 2026 Lakshya.
