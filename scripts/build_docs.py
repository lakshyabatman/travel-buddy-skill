#!/usr/bin/env python3
"""Refresh the card-coverage table inside docs/index.html. No site generator required."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required. pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / "cards"
DOCS = ROOT / "docs" / "index.html"
START = "<!-- COVERAGE:START -->"
END = "<!-- COVERAGE:END -->"


def coverage_html() -> str:
    rows = []
    files = sorted(CARDS_DIR.glob("*.yaml"))
    if not files:
        return "<p>No card files found.</p>"
    for path in files:
        doc = yaml.safe_load(path.read_text())
        country = doc.get("country") or path.stem
        code = doc.get("country_code") or ""
        label = f"{country} ({code})" if code else country
        programs = doc.get("programs") or {}
        table_checked = doc.get("table_last_checked") or ""
        for card in doc.get("cards") or []:
            prog = programs.get(card.get("program") or "", {})
            partners = prog.get("partners") or []
            n = len(partners)
            v = sum(1 for p in partners if p.get("verified") is True)
            u = n - v
            checked = card.get("last_checked") or table_checked
            ver = "yes" if card.get("verified") else "no"
            notes = []
            if u and v:
                notes.append(f"{v} of {n} partner ratios verified")
            elif n and not v:
                notes.append("partner ratios unverified")
            elif n and not u:
                notes.append("all listed partner ratios verified")
            rows.append(
                "<tr>"
                f"<td>{esc(label)}</td>"
                f"<td>{esc(card.get('name',''))}</td>"
                f"<td>{esc(prog.get('currency_name') or card.get('program') or '')}</td>"
                f"<td>{n}</td>"
                f"<td>{v}</td>"
                f"<td>{esc(str(checked))}</td>"
                f"<td>{esc(ver)}</td>"
                f"<td>{esc('; '.join(notes))}</td>"
                "</tr>"
            )
    thead = (
        "<table class=\"coverage\">\n"
        "<thead><tr>"
        "<th>Country</th><th>Card</th><th>Program</th>"
        "<th>Partners</th><th>Verified ratios</th>"
        "<th>Last checked</th><th>Card terms verified</th><th>Notes</th>"
        "</tr></thead>\n<tbody>\n"
    )
    return thead + "\n".join(rows) + "\n</tbody></table>"


def esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def splice(html: str, table: str) -> str:
    if START not in html or END not in html:
        sys.exit(f"{DOCS} is missing {START} / {END} markers")
    before, rest = html.split(START, 1)
    _, after = rest.split(END, 1)
    return f"{before}{START}\n{table}\n{END}{after}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true", help="Exit 1 if docs/index.html is stale")
    args = p.parse_args()
    html = DOCS.read_text()
    new = splice(html, coverage_html())
    if args.check:
        if new != html:
            print("docs/index.html coverage table is stale. Run: python scripts/build_docs.py", file=sys.stderr)
            return 1
        print("docs/index.html coverage table is up to date")
        return 0
    if new != html:
        DOCS.write_text(new)
        print(f"Updated {DOCS}")
    else:
        print("No change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
