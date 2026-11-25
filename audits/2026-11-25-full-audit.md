# Full audit, 2026-11-25

Scope: the flight-points-optimiser skill on `main` after the price-history, watcher, quick mode,
award-link, freshness, landing-page, and eval commits. No personal trip, home city, balance, or
private card holding is used as an example. The licence name on `LICENSE` stays.

## (a) Price history

`search.py` downloads the Google Flights HTML that `fast-flights` already uses and reads two
things when they are present: the sentence "Prices are currently low/typical/high", and a daily
`[timestamp, price]` series in the `script.ds:1` JSON. The parsed flight list itself has no
price-insight object. A paid SearchAPI integration in the library does, and this project does
not call it.

Checked on a live LHR–JFK one-way page during development: 62 daily points, label "typical",
and a low/high pair in the same JSON block. That route was a probe, not a recommended trip.
If the graph is missing, the tools say so and point at the Price insights panel in the browser.
They do not invent points.

The local file `~/.flight-points-optimiser/history.jsonl` (or `$FLIGHT_POINTS_HISTORY`) stores
each search plus any graph. `history.py` reports min, median, max, a percentile band we define
(not Google's word), and the point count. The Buy now or wait step in `SKILL.md` says this is
not a forecast. Kayak advice and a Skyscanner month grid are called out as the wrong kind of
evidence. Tests cover extraction, an empty page, and the log.

## (b) Price watch

`watch.py` re-runs `search.py`, so the history log grows, and keeps the lowest fare in its own
state file. Exit 2 is a new low or a fare at or below `--threshold` that was not already
alerted. The first run only records a baseline unless the fare is already under the threshold.
A past departure date exits 0 without searching. It never books. Decision tests cover that.

## (c) Quick mode and length

`SKILL.md` leads with Quick mode: one question, about five searches, cash top 3, one points
line, then an offer to go deeper. The long workflow is under Full mode, with the repeated
airport catalogue and sample tables removed. `AGENTS.md` and `prompts/any-llm.md` lead the
same way. `search.py`, `history.py`, and `watch.py` are described as an optional scraper the
skill does not need.

Line count: 426 immediately before this rewrite, 161 after. The file on `af34b75`, before the
history section was added, was 396.

## (d) Awards

Most agents cannot log in. The skill says the seat is not checked unless it was seen.
`awards/links.yaml` has templates, a source, and `last_checked`. Aeroplan's one-way redeem URL
returned HTTP 200 with origin, destination, date, and adult count, so that template is
`verified: true`. KrisFlyer, British Airways, and Cathay pages opened with no confirmed query
parameters, so they are search homes only. United's `f`, `t`, `d`, `px` pattern is included as
`verified: false` because this environment could not re-fetch United. Cabin and return date are
not in the templates. `awards.py` prints the link and a 30-second checklist and says the link
is not availability.

## (e) Card freshness

`.github/workflows/card-freshness.yml` runs Mondays and on demand. Permissions are
`contents: read` and `issues: write` only. It opens or updates one issue titled "Card data:
stale or unverified entries", and closes that issue when the report is clean. A local run on
this date found 0 stale rows and 24 unverified ones, mostly HDFC partners that were already
marked `verified: false` and the Amex India block.

`CONTRIBUTING.md` names the next batch as not researched: IDFC FIRST Wealth and Ashva, ICICI
Emeralde and Sapphiro, and the other Axis columns (Reserve, Olympus, Burgundy Private). Magnus,
Magnus for Burgundy, and Mayura are already in `cards/india.yaml` from official pages. Mayura
has an empty partner list because the bank says the points do not transfer.

## (f) Landing page

`docs/index.html` opens with the pitch, three benefits, and one install command. The worked
example is a fictional Lisbon–São Paulo trip for two adults. The numbers are labelled as a
sample and stored in `docs/example.json`. A dashed box is the GIF slot; no image is pretended.
`python scripts/build_docs.py --check` still passes. The page links the repo and the Pages URL.

## (g) Evals

`evals/cases.yaml` has 13 prompts: a quick ask, "anywhere", fixed dates, flexible dates, a
split return, several passengers, a self-transfer visa question, a basic-fare bag, a stale card
file, a prompt-injection paste, an award-space question, buy-or-wait with no history, and a
price watch. `python evals/run.py` prints them. `--check` only validates the file and is what
CI runs. Scoring is manual in `evals/SCORE.md`.

## (h) Hard rules and neutrality

The skill still refuses to book, pay, or transfer without a yes, and to invent fares, fees,
ratios, visas, or history. Examples in the skill, the prompt, the docs, and the evals are
generic city pairs. A scan found no personal itinerary, balance, or "cards I hold" line. The
copyright name on the licence is the only personal name kept.

## Fixes in this audit commit

- `search.py --help` no longer uses one country's airport codes as the sample.
- `.gitignore` now ignores copies of `history.py`, `watch.py`, and `awards.py` that
  `install.sh --project` would drop inside this repo.

## Checks

`python -m unittest discover -s tests -q`, `python evals/run.py --check`,
`python scripts/validate_cards.py`, `python scripts/build_docs.py --check`,
`python search.py --help`, `python history.py --help`, `python watch.py --help`,
`python awards.py --help`, and `bash -n scripts/install.sh`.
