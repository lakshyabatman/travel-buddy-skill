# Card transfer files

One YAML file per card-issuing **country**: `cards/india.yaml`, `cards/us.yaml`, and so on.
ISO 3166-1 alpha-2 codes are preferred in `country_code` (`IN`, `US`, `GB`).

v1 ships **India only** (`cards/india.yaml`). That is one issuing country, not a default route, currency, or passport. Other countries are planned; see the backlog in `CONTRIBUTING.md`.
Do not invent a file from memory. Add a country only from official issuer pages, with
`verified` and `last_checked` on every card and partner.

## Schema

- `schema_version`: currently `1`. Bump only when required fields or key names change.
- `country`, `country_code`: human name and ISO code.
- `table_last_checked`: date the file as a whole was last reviewed (`YYYY-MM-DD`).
- `programs`: map of reward currencies (issuer, currency name, transfer portal, partners).
- `cards`: products that earn a program. Each has `id`, `name`, `program`, `caps`, `fees`,
  `source_url`, `last_checked`, `verified`.
- Every partner needs `name`, `ratio` (string `"card_points:partner_points"`, e.g. `"2:1"`),
  `verified` (bool) and `last_checked`. Put `source_url` on the partner, or a shared
  `partners_source_url` on the program when every row comes from one official table.
- `verified: true` only if the number was read on an official bank/issuer (or partner-about-bank)
  page on `last_checked`. Otherwise `false`, with a URL and a note. Use `null` when unknown.
- Formal schema: [`../schemas/cards.schema.json`](../schemas/cards.schema.json).
  Validate with `python scripts/validate_cards.py`.

Ratios are written **card points : partner points**. `2:1` means two card points become one mile.
