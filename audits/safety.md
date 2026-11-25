# Audit: safety

Date: 2026-11-25 (Asia/Calcutta). Scope: every user-facing file — `SKILL.md`, `AGENTS.md`,
`prompts/any-llm.md`, `README.md`, `docs/index.html`, Cursor / Claude adapters,
`scripts/install.sh`, `search.py`, and the card workflow.

## Rules under test

1. Never book, pay, or transfer points without explicit user go-ahead for that exact action.
2. Never invent fares, award prices, taxes or ratios; cite a source; label unverified figures.
3. Transfers are described as irreversible.
4. Award space must be checked on the partner site before a transfer is recommended.
5. Examples must not be mistaken for live quotes.

## Findings

- `SKILL.md` leads with the hard rules, repeats the go-ahead line in the booking steps and
  the price-watch step, and ends with a checklist item that nothing was booked or transferred.
  Award-space and unverified-labelling rules are present. **Pass.**
- `AGENTS.md`, the Cursor rule, and `prompts/any-llm.md` all repeat the no-booking / no-invention
  rules. The paste-in prompt also tells the model to end by saying it has not booked or transferred
  anything. **Pass.**
- `README.md` and the docs site state the same limits, plus the disclaimer that ratios change and
  must be confirmed in the bank portal. **Pass.**
- `scripts/install.sh` only copies files onto the local machine. Its header says it never books
  or pays. `--force` is required to overwrite. **Pass.**
- `search.py` only fetches public Google Flights HTML and prints a table/JSON. It tells the user
  to re-check before booking and does not open a checkout. **Pass.**
- Card files include `reversible: false` and transfer-time caveats. **Pass.**

## Issues and fixes

1. **Example fares could be mistaken for live quotes.** The ranked-table illustration in
   `SKILL.md` originally used a real LHR–JFK cash figure from the same day's test. **Fix:**
   replaced with clearly fictional airline names (XX / YY) and round placeholder amounts, and
   kept the line "The rows below only show the format; never reuse their numbers." The docs
   site example is behind a banner: "This is a fictional example for illustration only. Do not
   use these fares, taxes, or ratios to book or transfer points."
2. **No paid-API footgun in CI.** The live `search.py` smoke test in GitHub Actions is
   `continue-on-error: true`, so a Google block cannot be "fixed" by adding a paid API key.
   **No change needed.**

## Verdict

The no-booking, no-transfer, and no-fabrication rules hold everywhere a user or agent would
read them. The only fix was making examples unmistakably fictional.
