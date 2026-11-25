# Security

## Reporting a vulnerability

Please report security issues privately through GitHub Security Advisories:

https://github.com/lakshyabatman/travel-buddy-skill/security/advisories/new

That page is available once the repository owner enables private vulnerability
reporting. Until then, contact the owner directly and do not open a public
issue that includes exploit details.

Do not put passwords, card numbers, session cookies, or API keys in a report.

## What belongs here

This repository is an instruction file plus local helpers. It does not run a
hosted service and it does not take payment. Issues that matter:

- Instructions that let a web page override the skill (prompt injection),
  including text that claims the user already agreed to book, pay, or transfer
  points.
- Helpers that store personal data or secrets, or that write outside the
  documented history and watch files.
- `scripts/install.sh` following symlinks or overwriting files without
  `--force`.
- Workflow or dependency changes that widen GitHub Actions permissions, float
  a package version, or pass untrusted input into `run:`.

`fast-flights` and `primp` are an unofficial scraper. A bug in those pinned
packages is in scope if this repo can avoid it with validation, a timeout, or
a version pin. There is no bug-bounty budget.

## Supported versions

The default branch (`main`) is the only supported line.
