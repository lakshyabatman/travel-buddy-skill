#!/usr/bin/env python3
"""Fill an award-search link from awards/links.yaml. Never checks availability."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required. pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parent
LINKS = ROOT / "awards" / "links.yaml"


def load():
    doc = yaml.safe_load(LINKS.read_text())
    if not isinstance(doc, dict):
        raise ValueError("awards/links.yaml is not a mapping")
    return doc


def find(doc, programme):
    key = programme.strip().lower().replace(" ", "_")
    for item in doc.get("programmes") or []:
        if item.get("id") == key or item.get("name", "").lower() == programme.strip().lower():
            return item
    return None


def build(item, origin, dest, depart, adults):
    if not item.get("supports_prefill") or not item.get("template"):
        return None
    return item["template"].format(
        origin=origin.upper(),
        destination=dest.upper(),
        depart=depart,
        adults=int(adults),
    )


def main(argv=None):
    p = argparse.ArgumentParser(description="Print an award-search link. Does not check space.")
    p.add_argument("programme")
    p.add_argument("origin", nargs="?")
    p.add_argument("dest", nargs="?")
    p.add_argument("date", nargs="?")
    p.add_argument("--adults", type=int, default=1)
    a = p.parse_args(argv)
    doc = load()
    item = find(doc, a.programme)
    if item is None:
        print("No template for %r. Use that programme's own award search. Space was not checked." % a.programme, file=sys.stderr)
        return 2
    print(item["name"])
    if item.get("verified") is not True:
        print("URL shape was NOT re-checked on %s. Treat it as unverified." % item.get("last_checked"))
    link = None
    if a.origin and a.dest and a.date and item.get("supports_prefill"):
        link = build(item, a.origin, a.dest, a.date, a.adults)
        print(link)
    else:
        print(item.get("search_url"))
        print("This programme has no confirmed prefilled URL. Enter the route, dates, cabin, and passengers yourself.")
    if item.get("limits"):
        print(item["limits"])
    print("Checklist:")
    for step in doc.get("checklist") or []:
        print("- " + step)
    print("This link does not mean a seat is available.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
