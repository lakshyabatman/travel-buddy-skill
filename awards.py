#!/usr/bin/env python3
"""Fill an award-search link from awards/links.yaml. Never checks availability."""
from __future__ import annotations

import argparse
import string
import sys
from pathlib import Path

import inputs

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required. pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parent
LINKS = ROOT / "awards" / "links.yaml"


class NoAliasLoader(yaml.SafeLoader):
    def ignore_aliases(self, _data):
        return True


def load():
    doc = yaml.load(LINKS.read_text(), Loader=NoAliasLoader)
    if not isinstance(doc, dict):
        raise ValueError("awards/links.yaml is not a mapping")
    return doc


def find(doc, programme):
    key = programme.strip().lower().replace(" ", "_")
    for item in doc.get("programmes") or []:
        if item.get("id") == key or item.get("name", "").lower() == programme.strip().lower():
            return item
    return None


def fill_template(template, fields):
    """Substitute only the four named placeholders. No attribute access."""
    if not isinstance(template, str) or len(template) > 2000:
        raise ValueError("template must be a short string")
    allowed = {"origin", "destination", "depart", "adults"}
    for _, field_name, format_spec, conversion in string.Formatter().parse(template):
        if field_name is None:
            continue
        if conversion or format_spec or field_name not in allowed:
            raise ValueError("unsafe or unknown placeholder in award template")
    return template.format(**fields)


def build(item, origin, dest, depart, adults):
    if not item.get("supports_prefill") or not item.get("template"):
        return None
    origin = inputs.iata(origin, "origin")
    dest = inputs.iata(dest, "destination")
    when = inputs.iso_date(depart, "departure date")
    count = inputs.bounded_int(adults, "adults", None, 1, 9)
    return fill_template(
        item["template"],
        {"origin": origin, "destination": dest, "depart": when.isoformat(), "adults": count},
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
    print(inputs.one_line(item.get("name"), 120))
    if item.get("verified") is not True:
        print("URL shape was NOT re-checked on %s. Treat it as unverified." % inputs.one_line(item.get("last_checked"), 20))
    link = None
    if a.origin and a.dest and a.date and item.get("supports_prefill"):
        try:
            link = build(item, a.origin, a.dest, a.date, a.adults)
        except ValueError as exc:
            print(inputs.one_line(exc), file=sys.stderr)
            return 2
        print(link)
    else:
        print(inputs.one_line(item.get("search_url"), 500))
        print("This programme has no confirmed prefilled URL. Enter the route, dates, cabin, and passengers yourself.")
    if item.get("limits"):
        print(inputs.one_line(item["limits"], 500))
    print("Checklist:")
    for step in doc.get("checklist") or []:
        print("- " + inputs.one_line(step, 300))
    print("This link does not mean a seat is available.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
