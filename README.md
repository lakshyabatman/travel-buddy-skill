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
- try flexible dates (only after asking; ±3 days if it cannot ask), nearby and secondary
  airports, positioning hops to better-connected hubs, open-jaw tickets, rail-plus-air, and
  separate tickets via hubs;
- ask about bags, seats, and changes, then rank by the **true total** (base fare plus the fees
  the traveller would really pay). Unknown fees stay unknown. A few official fee snapshots live
  in `fees/`;
- ask each traveller's passport nationality and any visa they already hold, then flag transit
  and entry from official sources (OK / needs X / check). There is no default passport;
- compare each card's transfer partners using `cards/<country>.yaml`: points needed, taxes,
  value per point, caps, fees, transfer times (and research the issuer live if that country or
  card has no file yet);
- lead with up to three picks (Cheapest, Best trip, Best points value (check seat)), then one table of cash, points, other dates, and other airports;
- optionally set up a price-watch routine that alerts only on real drops.

It **never books, pays, or transfers points** without your explicit go-ahead, and it must cite a
source for every fare, fee, ratio, and visa rule.

`SKILL.md` is the source of truth. Adapters for Claude Code, Cursor, Codex / `AGENTS.md` readers,
and a paste-in prompt for any LLM all point back at it.

Card files are one per issuing country. v1 includes `cards/india.yaml` only (HDFC Infinia,
HDFC Diners Club Black, Axis Atlas, Amex India Membership Rewards). That file is not a default
route or passport. Other countries are researched from the issuer and labelled unverified until
someone adds a file; see `CONTRIBUTING.md`.

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

Then ask, for example (three regions, none of them a default):

> Cheapest way from Mexico City to Madrid around 10 March, economy, 1 adult, in MXN.
> Cabin bag only, any seat, I don't need free changes. Passport: Mexico. No other visas.

> Cheapest way from Singapore to Sydney, ±3 days, 2 adults, in AUD. One 20 kg checked bag each,
> sit together. Passports: Singapore.

> Cheapest way from Nairobi to Paris, one way, in EUR. Ask me how flexible the dates are before
> you search. Passport: Kenya. I also hold a Schengen visa.

## search.py (optional)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python search.py MEX MAD 2026-12-16 --currency MXN
python search.py SIN SYD 2027-02-05 --flex 3 --currency AUD --top 15
python search.py NBO CDG 2027-01-10 --return 2027-01-17 --currency EUR
python search.py GRU LIS 2027-03-01 --json-only > out.json
```

`--currency` is passed through to Google Flights (ISO 4217, for example `USD`, `EUR`, `GBP`,
`MXN`, `BRL`, `AUD`, `KES`). If you omit it, Google chooses. The script does not convert
currencies itself.

It prints a price-sorted table and a "cheapest per origin/date" view, followed by JSON (use
`--json-only` for agents). Prices are totals for all passengers as shown by Google Flights at
fetch time.

Notes:
- `fast-flights` is an unofficial scraper. It was tested working on 2026-11-25 (v3.1.0) on
  LHR–JFK and SIN–SYD. Those were test routes, not preferred origins. It can break or be
  rate-limited at any time. If it fails, use Google Flights, Skyscanner or Kayak in a browser.
- A round trip fetches the return for the top few outbound options (`--return-picks`,
  default 3, max 5). The price is the round-trip total from that second search. If the
  return cannot be fetched, the row says `likely return flights (schedule only, not
  price-linked)` or `return not fetched`. Elapsed time includes layovers. An airport code
  with no usable result is retried as its metro city code (`HND` → `TYO`).
  `--origin-airports` and `--dest-airports` search several airports and merge them. Still
  cross-check a round trip in a browser.
- `--delay` (default 1.5 s) spaces out requests. Keep `--flex` × airports small.

`search.py` is an optional, unofficial scraper. The skill works without it. When a search
response contains Google's price-history graph, the script stores that graph plus the fare in
`~/.flight-points-optimiser/history.jsonl` (override with `--history` or
`$FLIGHT_POINTS_HISTORY`). The directory is mode 0700 and the file is mode 0600, including
an existing file the next time it is written. It stores
the route, dates, cabin, passenger counts, currency, and price. It does not store names,
passport numbers, or card numbers. `python history.py ORIG DEST YYYY-MM-DD` prints min,
median, max, and where the latest point sits. If the graph is missing, it says so. That is
not a forecast. `watch.py` keeps the same kind of record in
`~/.flight-points-optimiser/watch-ORIGIN-DEST-DATE.json`. Both names are gitignored if a
run is pointed at this repo.

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

The script checks every `cards/*.yaml` against `schemas/cards.schema.json` and every
`fees/*.yaml` against `schemas/fees.schema.json`, and warns when `last_checked` is more than 60
days old. GitHub Actions runs this plus the unit tests and a `search.py` smoke test
(see `.github/workflows/ci.yml`). A weekly job lists stale or unverified entries in an issue.

Before a release, run `python evals/run.py` and fill in `evals/SCORE.md`. See `evals/README.md`.

## Disclaimer

**Transfer ratios, partners, caps and fees change often, sometimes overnight and without notice.**
Card files record where and when each number was checked; entries marked `verified: false` come
from blogs, or from official pages that are old or behind a login. **Always confirm the ratio
in your bank's transfer portal, and confirm award seat availability on the airline programme's
site, before transferring.** Point transfers are almost always irreversible. This project is not
affiliated with any bank, airline or loyalty programme, and nothing here is financial advice.

## License

MIT, see [LICENSE](LICENSE). Copyright (c) 2026 Lakshya.
