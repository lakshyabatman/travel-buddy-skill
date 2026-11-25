# Award-search links

`links.yaml` holds public award-search URLs. A link is not availability.

- `supports_prefill: true` means the template can take an origin, destination, departure date, and adult count.
- `verified: true` means that URL shape was opened from this environment on `last_checked`.
- `verified: false` is a lead. Say so. Do not claim the seat exists.
- Cabin and return dates are not in these templates. The user sets those on the page.
- Programmes that are not listed have no confirmed template. Send the user to that programme's own site.

`python awards.py aeroplan LIS GRU 2026-12-10 --adults 2` prints a link and the 30-second checklist.

`charts.yaml` lists a programme only when an official published chart URL was identified.
JAL's own international chart is there, unverified from this environment (jal.co.jp returned
403). A JAL partner chart was not confirmed and is omitted. No extra airline fee files were
added in that pass: a fee file needs an official fee page that was opened and cited.
