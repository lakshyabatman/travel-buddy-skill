# Security audit

Date: 2026-11-25. Scope: `SKILL.md`, `AGENTS.md`, `prompts/any-llm.md`, the Cursor rule,
`search.py`, `history.py`, `watch.py`, `awards.py`, `scripts/install.sh`, the validators and
docs builder, `evals/run.py`, GitHub Actions, `requirements.txt`, `docs/index.html`, and git
history. No secrets were printed while scanning.

There is no critical finding. Nothing in the tree or the git history is a token, a private
key, or a password. The helpers do not use `eval`, `exec`, `pickle`, or `shell=True`.

## Findings

### High

1. **Fetched pages could override the skill.** The skill tells an agent to read Google
   Flights, airline sites, blogs, bank pages, immigration pages, and the Firecrawl
   Alexandria page. Those pages are untrusted. The hard rules said not to book or invent
   numbers, and they did not say that page text is data. A page (or a paste of a page) can
   say "the user already agreed" or "the fare is exactly 1". That is not consent and it is
   not a fare. `evals/cases.yaml` already had a prompt-injection case; the instructions the
   agent reads did not match it.
2. **`watch.py` built a filesystem path from the origin argument.** The state file was
   `~/.flight-points-optimiser/watch-<origin>-<dest>-<date>.json`. An origin of `../..`
   left that directory. An agent that copies a route out of a page would pass that string
   straight through.

### Medium

3. **Price history and watch state were created with the process umask** (often mode 0644)
   and the write followed symlinks. The files are only route and price, but a travel log is
   still private, and a symlink at the destination would append into another file.
   `record_observation` also stored whatever dict it was given, so a later caller could have
   added a passport number or a card number.
4. **CLI arguments were not checked.** Airport codes, dates, currency, passenger counts, and
   `--history` were passed into the scraper and the log. A currency or airport value with
   extra characters changes the Google query. `awards.py` filled URL templates with
   `str.format`, which follows attribute names in the template (`{origin.__class__}`).
5. **The Google fetch had no timeout.** `fast-flights` builds a `primp` client without
   `timeout`. `primp` does not use Python's socket timeout, so a hung connection stalls
   `search.py` and `watch.py`.
6. **Dependencies and Actions floated.** `requirements.txt` used ranges (`fast-flights>=3.1,<4`,
   `pyyaml>=6`). CI used `actions/checkout@v4` and `actions/setup-python@v5`. The weekly job
   ran `pip install pyyaml` with no version. `fast-flights` and `primp` are an unofficial
   scraper; an unpinned bump is a supply-chain change.
7. **`scripts/install.sh` followed a destination symlink.** `--force` wrote through
   `~/.claude/skills/flight-points-optimiser` when that path was a symlink. `cp -R` also
   follows a top-level source symlink, so a `cards` symlink to another directory would be
   copied in full. The unquoted heredoc would expand `$(...)` if the repo path contained it.

### Low

8. **The weekly issue closed on a substring.** The workflow treated the report as clean when
   the body contained the sentence "Nothing stale or unverified." A card name or URL that
   included that sentence would close the tracking issue and hide the findings.
9. **The docs page had no Content-Security-Policy and external links had no `rel`.** There
   is one inline script. It already uses `textContent` and `fetch("example.json")` on the
   same origin, so it does not interpret the JSON as HTML. There is no third-party script,
   so SRI does not apply. The hero loads one image from `media.tenor.com`. An image cannot
   run script, but it is a third-party request. GitHub Pages will still run Jekyll unless
   `.nojekyll` is present.
10. **No `SECURITY.md` and no Dependabot config.**
11. **`scripts/validate_cards.py` would open any path it was given**, including a file
    outside the repo.

### Informational

- Git history has no API keys or private keys. The initial commit records the maintainer as
  the git author. That is normal public metadata. Examples and `docs/example.json` are
  fictional routes (Lisbon–São Paulo, Mexico City–Madrid, and others). They do not contain
  the maintainer's email, a balance, or a trip.
- `install.sh` already had `set -euo pipefail`, did not use `curl | bash` or `sudo`, and
  refused to overwrite without `--force`.
- YAML was already loaded with `SafeLoader` (or `yaml.safe_load`). Loaders now also ignore
  aliases so a file cannot expand itself.
- CI `run:` steps do not interpolate `${{ github.event.* }}`. There is no
  `pull_request_target`.
- The weekly workflow already limited itself to `contents: read` and `issues: write`.
  `contents: read` has to stay: `actions/checkout` fails without it. `issues: write` is the
  only write. The job does not run on pull requests, so it does not execute PR code.
- The live Google smoke test is `continue-on-error: true`, so a block does not tempt anyone
  to add a paid API key.

## What this PR changes

- `SKILL.md`, `AGENTS.md`, `prompts/any-llm.md`, the Cursor rule, and the `AGENTS.md` block
  written by `install.sh` now say that page text and tool JSON are data, not instructions
  and not consent. They also forbid asking for or storing passwords, one-time codes, full
  card numbers, CVVs, loyalty logins, passport numbers, and API keys.
- `watch.py` accepts only 3-letter IATA codes in the default state name, refuses a state
  file whose name does not start with `watch`, and writes mode 0600 without following a
  symlink. The subprocess is a list (`shell=False`) with a 300 second timeout.
- `history.py` writes `~/.flight-points-optimiser/history.jsonl` as mode 0600 under a
  directory mode 0700. The record is an allowlist: route, dates, cabin, passenger counts,
  currency, price, source, timestamp, and the numeric Google graph. Symlinks and credential
  directories (`.ssh`, `.gnupg`, `.aws`, and similar) are refused. Paths must stay under the
  home directory, the current directory, or the temp directory.
- `search.py` checks IATA codes, dates, currency, counts, `--flex`, `--delay`, and `--top`
  before any network call. The fetch sets a 20 second primp timeout and refuses a body over
  4MB. Errors copied into JSON are one line and truncated, so a parser exception cannot
  paste a page into the agent's context.
- `awards.py` only substitutes `{origin}`, `{destination}`, `{depart}`, and `{adults}`.
- `requirements.txt` pins the tree that resolved on 2026-11-25, including `fast-flights==3.1.0`
  and `primp==2.0.1`. Hashes are not set: several wheels are platform-specific, and a
  linux-only hash list would break `pip install` on macOS. Exact versions plus Dependabot
  are the pin. Review bumps of `fast-flights` and `primp` before merging.
- Both workflows pin Actions to commit SHAs, set `persist-credentials: false`, and install
  from `requirements.txt`. CI permissions are `contents: read`. The weekly job's clean check
  is the first line `status: clean`, not a substring of the body.
- `docs/index.html` has a CSP (`script-src` is the hash of the inline script, not
  `'unsafe-inline'`). `img-src` allows only this site and `https://media.tenor.com` for the
  hero GIF. Outbound links, including the Tenor credit, use `rel="noopener noreferrer"`.
  `docs/.nojekyll` stops Jekyll from rewriting the page.
- `SECURITY.md` and `.github/dependabot.yml` (pip and github-actions, weekly).
- `tests/test_security.py` covers the private file mode, dropped secrets, symlink refusal,
  path escape, CLI rejection, the fetch timeout, the watch path, and the award template.

## Checks run

`python -m unittest discover -s tests -t .` (26 tests), `python evals/run.py --check`,
`python scripts/validate_cards.py` (0 errors), `python scripts/build_docs.py --check`,
`search.py --help`, and a temporary-home run of `scripts/install.sh` (symlink destination
refused, `--force` replaces the symlink without writing through it, a source symlink is
refused, a second install without `--force` does not overwrite). The live Google scrape was
not required for these checks. CI still runs it as `continue-on-error`.

## What the owner must turn on

These are repository settings. A pull request cannot change them.

1. **Secret scanning and push protection.** Settings → Code security → Secret scanning, and
   push protection. The history scan was clean; push protection is what stops a later commit.
2. **Branch protection on `main`.** Require a pull request, require the CI check, and block
   force-pushes. Direct pushes to `main` skip review of workflow and dependency changes.
3. **Private vulnerability reporting.** Settings → Code security → Private vulnerability
   reporting. `SECURITY.md` links to the advisory form, which stays hidden until this is on.
4. **Dependabot security updates**, in the same settings area. `.github/dependabot.yml`
   only opens version bumps. Security updates are the setting that opens alerts for known
   vulnerabilities in the pinned packages.

`frame-ancestors` is not set. A CSP `<meta>` tag is not allowed to set it, and GitHub Pages
does not offer a custom response header. The page does not embed itself in a frame for any
feature here.
