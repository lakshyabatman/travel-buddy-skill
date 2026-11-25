# Contributing

The most valuable contribution is keeping card-transfer data accurate and adding new countries
in batches. Issuers add and remove transfer partners (partners also opt out), move partners
between cap groups, and cut ratios, often overnight and without announcements. A stale ratio
can cost someone a lot of points, because transfers cannot be reversed.

`SKILL.md` is the workflow source of truth. Do not fork a second copy of the steps in an
adapter; point adapters at `SKILL.md` and refresh installed copies with `scripts/install.sh`.

## Ground rules for card data

- **Official sources first.** A ratio is `verified: true` only if you read it on the bank's or
  issuer's own page, or on the partner programme's official page about that bank, on the date
  in `last_checked`. Put that URL in `source_url` (or a program-level `partners_source_url`).
- Blog or aggregator only, an official page that's years old, or a page behind a login:
  `verified: false`, with the URL and a short note.
- **Never guess.** If you can't find a value, use `null` and explain in `notes`.
- Write ratios as `"card_points:partner_points"` (`"2:1"` = 2 card points for 1 mile).
- Use ISO dates (`YYYY-MM-DD`) for `last_checked`.
- One file per card-issuing country: `cards/india.yaml`, `cards/us.yaml`, … See `cards/README.md`
  and `schemas/cards.schema.json`.

## Refreshing an existing card or country file

1. Open the card's `source_url` (and the program's `general_sources`).
2. Compare every partner, ratio, cap, fee and transfer time. Remove partners that are gone and
   move them to `removed_partners` with the date you noticed.
3. Update `last_checked` on everything you re-read (and `table_last_checked` at the top).
4. Run `python scripts/validate_cards.py` and `python scripts/build_docs.py` (refreshes the
   coverage table in `docs/index.html`).
5. In your PR description, list what changed, with links. Example: "Axis Atlas: Qatar 1:2 -> 2:1".

## Adding a batch of new cards (or a new country)

1. If this is a new country, create `cards/<country>.yaml` with `schema_version: 1`,
   `country`, `country_code`, `table_last_checked`, `programs` and `cards`.
2. Add the reward currency under `programs:` if it's new (issuer, currency name, transfer
   portal, minimums, partners, sources). Cards that share a currency and ratios share one
   program entry.
3. Add one entry per card under `cards:` with `id`, `name`, `program`, `caps`, `fees`, `notes`,
   `source_url`, `last_checked`, `verified`. Put card-specific ratios in the card entry if they
   differ from the program's.
4. Remove the item from the backlog below once it is covered.
5. Validate and regenerate the docs table:
   ```bash
   python scripts/validate_cards.py
   python scripts/build_docs.py
   ```
6. Bump `schema_version` **only** if you change the structure (new required fields, renamed
   keys), and describe the change in the PR.

## Planned country batches (not in v1)

Please contribute these as separate PRs, official sources only:

- **United States:** American Express Membership Rewards, Chase Ultimate Rewards, Citi ThankYou,
  Capital One Miles, Bilt Rewards
- **United Kingdom:** American Express UK Membership Rewards (and other UK transferable
  currencies if official tables are available)
- **UAE**
- **Singapore**
- **Canada**
- **Australia**

India (`cards/india.yaml`) is the v1 file. It includes Magnus, Magnus for Burgundy, and
IDFC FIRST Mayura alongside the earlier cards.

## Next Indian batch (not researched yet)

Official issuer pages only. Do not copy a blog, and do not mark `verified: true` until you have
read the ratio on that page. If a card has no airline transfer programme, say so and leave
`partners` empty.

- **IDFC FIRST:** Wealth and Ashva. Mayura is already in the file and does not transfer.
- **ICICI:** Emeralde and Sapphiro.
- **Axis:** Reserve, Olympus, and Burgundy Private are other columns of the Travel EDGE table.
  Magnus and Magnus for Burgundy are already in the file.

A weekly workflow (`.github/workflows/card-freshness.yml`) opens or updates an issue listing
stale and unverified entries. It only has permission to read the repo and write issues.

## Airline fee snapshots

`fees/*.yaml` holds a few dated readings of official airline fee pages. See `fees/README.md`
and `schemas/fees.schema.json`. Add a file only for figures you read on the airline's own page,
with `source_url`, `last_checked`, and `verified: true`. Do not copy a blog, and do not turn one
country's fees into a default. Run `python scripts/validate_cards.py` after editing.

## search.py and docs

`fast-flights` scrapes Google Flights and breaks when Google changes its page. If it stops
working, open an issue with the error and the `fast-flights` version. Pin a working version in
`requirements.txt` when you fix it. `--currency` is a real `fast-flights` / Google Flights
option; do not fake currency conversion in the script.

The GitHub Pages site is the static file `docs/index.html` (no site generator). After card
edits, run `python scripts/build_docs.py` so the coverage table stays in sync. CI can run
`python scripts/build_docs.py --check`.
