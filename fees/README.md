# Airline fee snapshots

Optional, dated readings of **official** airline fee pages. They are examples of how to record a
fee, spread across regions. They are **not** a default airline, country, or passport, and they
are not a complete fee database.

`SKILL.md` still requires a live check of the airline's own fee page or the fare-brand details
at checkout for the itinerary you are pricing. A snapshot is a head start only. If it is missing,
stale (older than about 60 days), or for a different market, do not reuse its numbers: read the
official page, or say the fee is **unknown**. Never guess. A blog or a memory is **unverified**.

## File shape

One YAML file per snapshot, validated against `schemas/fees.schema.json` by
`python scripts/validate_cards.py`.

- `airline`, `iata`, `region` (the market the page describes), `currency`
- `source_url` (the official page), `last_checked` (`YYYY-MM-DD`), `verified`
- `fare_brands[]`: `name`, and only the fee lines you actually read (`cabin_bag`, `checked_bag`,
  `seat_selection`, `changes`, `refunds`, `payment_surcharge`, `booking_fee`). Each line has a
  `summary`. Omit a line you did not read. `null` means you looked and the page did not state it.

`verified: true` is only for a figure you read on that official page on `last_checked`.

## Snapshots in this folder

| File | Market | What was read |
|---|---|---|
| `southwest.yaml` | United States mainland (Southwest) | Checked-bag table, change and cancel fees, paid seat range, on the airline's optional-charges page |
| `jetstar.yaml` | Jetstar Airways / Jetstar Japan airport prices (Asia-Pacific) | Airport checked-bag and extra carry-on prices. Prepaid online bag prices vary by route and were **not** a single number on that page |

Add another region by reading that airline's official page and opening a pull request. Do not
copy a fee from a blog, from memory, or from a different airline's file.
