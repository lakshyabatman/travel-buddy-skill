#!/usr/bin/env python3
"""Markdown list of stale or unverified card and fee entries. Always exits 0."""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required. pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parents[1]
STALE_DAYS = 60


class DateAsStringLoader(yaml.SafeLoader):
    def ignore_aliases(self, _data):
        return True


def one_line(value) -> str:
    return " ".join(str(value).replace("`", "'").split())[:200]


for _ch, _resolvers in list(DateAsStringLoader.yaml_implicit_resolvers.items()):
    DateAsStringLoader.yaml_implicit_resolvers[_ch] = [
        (tag, regexp) for tag, regexp in _resolvers if tag != "tag:yaml.org,2002:timestamp"
    ]


def load(path: Path):
    return yaml.load(path.read_text(), Loader=DateAsStringLoader)


def age(raw):
    try:
        checked = datetime.strptime(str(raw), "%Y-%m-%d").date()
    except ValueError:
        return None
    return (date.today() - checked).days


def main():
    stale = []
    unverified = []
    for path in sorted(p for p in (ROOT / "cards").glob("*.yaml") if not p.is_symlink()):
        doc = load(path)
        rel = path.relative_to(ROOT).as_posix()
        if not isinstance(doc, dict):
            continue
        if doc.get("table_last_checked"):
            days = age(doc["table_last_checked"])
            if days is not None and days > STALE_DAYS:
                stale.append(f"- `{rel}` table_last_checked {one_line(doc['table_last_checked'])} ({days} days)")
        for pid, prog in (doc.get("programs") or {}).items():
            for partner in prog.get("partners") or []:
                label = one_line(f"{rel} {pid} / {partner.get('name')}")
                days = age(partner.get("last_checked"))
                if days is not None and days > STALE_DAYS:
                    stale.append(f"- {label}: last_checked {partner.get('last_checked')} ({days} days)")
                if partner.get("verified") is False:
                    unverified.append(f"- {label}: unverified ({one_line(partner.get('source_url') or 'no source')})")
        for card in doc.get("cards") or []:
            label = one_line(f"{rel} card {card.get('id')}")
            days = age(card.get("last_checked"))
            if days is not None and days > STALE_DAYS:
                stale.append(f"- {label}: last_checked {card.get('last_checked')} ({days} days)")
            if card.get("verified") is False:
                unverified.append(f"- {label}: unverified ({one_line(card.get('source_url') or 'no source')})")
    for path in sorted(p for p in (ROOT / "fees").glob("*.yaml") if not p.is_symlink()):
        doc = load(path)
        if not isinstance(doc, dict):
            continue
        rel = path.relative_to(ROOT).as_posix()
        days = age(doc.get("last_checked"))
        if days is not None and days > STALE_DAYS:
            stale.append(f"- `{rel}` last_checked {doc.get('last_checked')} ({days} days)")
        if doc.get("verified") is False:
            unverified.append(f"- `{rel}`: unverified")

    print("status: clean" if not stale and not unverified else "status: findings")
    print(f"Card and fee freshness report, {date.today().isoformat()}.")
    print()
    print("Stale means `last_checked` is more than 60 days old. Unverified means `verified: false`.")
    print("Confirm ratios on the issuer's page before transferring points. This issue does not change any balance.")
    print()
    if not stale and not unverified:
        print("Nothing stale or unverified.")
        return 0
    print(f"## Stale ({len(stale)})")
    print("\n".join(stale) if stale else "_None._")
    print()
    print(f"## Unverified ({len(unverified)})")
    print("\n".join(unverified) if unverified else "_None._")
    return 0


if __name__ == "__main__":
    sys.exit(main())
