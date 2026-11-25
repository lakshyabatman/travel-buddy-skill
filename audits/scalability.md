# Audit: scalability and maintainability

Date: 2026-11-25 (Asia/Calcutta). Scope: whether a contributor can add a new country batch,
keep ratios from going stale, and change the workflow in one place.

## What already supports scale

- One YAML file per card-issuing country (`cards/india.yaml` today; `cards/us.yaml` later),
  with `schema_version`, `country`, `country_code`, `last_checked` and `verified` on every
  card and partner.
- `schemas/cards.schema.json` plus `scripts/validate_cards.py` (schema, program references,
  verified-without-source, stale `last_checked` warnings, `--strict`).
- `scripts/build_docs.py` regenerates the public coverage table; `build_docs.py --check`
  fails CI if someone forgets to refresh `docs/index.html`.
- GitHub Actions (`/.github/workflows/ci.yml`) runs validation, the docs check, `search.py
  --help`, and a live search smoke test that does not fail the build if Google blocks the
  scraper.
- `CONTRIBUTING.md` describes refresh and batch-add steps, and lists planned country batches
  (US: Amex MR, Chase UR, Citi ThankYou, Capital One, Bilt; UK: Amex UK MR; UAE; Singapore;
  Canada; Australia).
- `SKILL.md` is the only workflow source of truth. Adapters and `AGENTS.md` point at it.
  The skill already says: if a country or card has no file, research the issuer live and
  label the result unverified; if `last_checked` is older than ~60 days, re-verify.

## Issues and fixes

1. **Country metadata was missing** from the India file after the move to `cards/`. **Fix:**
   added `country: India` and `country_code: IN` (additive, schema_version still 1). The
   schema marks these as recommended properties.
2. **Irregular `caps` and `fees` shapes** (string vs mapping) would have blocked a strict
   schema. **Fix:** the schema allows both, with `additionalProperties: true` on caps, fees
   and partners so a US or UK file can add fields (e.g. Chase 1:1 vs 1:2 UR) without a
   schema bump. A schema bump is only for renamed or newly required keys, as documented.
3. **Docs table would rot** as batches land. **Fix:** the generate-and-check script plus the
   CI `--check` step, and a CONTRIBUTING reminder to run `build_docs.py` after card edits.
4. **`search.py` defaulted to INR**, which is wrong for a global skill. **Fix:** `--currency`
  is a real `fast-flights` / Google Flights option (ISO 4217, including USD, GBP, EUR, INR,
  JPY, …). The default is now empty so Google chooses; the script does not invent a
  conversion.

## Remaining nits (not fixed)

- Partner `source_url` is still optional when the program has `partners_source_url`. That is
  deliberate for tables like Axis, but a future lint could warn when *neither* is present
  (the validator already errors if `verified: true` and no URL exists anywhere on the program).
- There is no automated fetch of official issuer pages. Re-verification stays a human (or
  agent) step, which is safer than scraping logins.

## Verdict

The layout is ready for country batches: add a file, validate, refresh the docs table, open a
PR. The 60-day stale warning and the "research live if missing" rule in `SKILL.md` are the
main defences against rotting data.
