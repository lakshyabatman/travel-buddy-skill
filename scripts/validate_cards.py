#!/usr/bin/env python3
"""Validate cards/*.yaml against schemas/cards.schema.json and flag stale dates."""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required. pip install -r requirements.txt")


class DateAsStringLoader(yaml.SafeLoader):
    """Keep ISO dates as strings so the schema can check YYYY-MM-DD."""


# Drop the implicit timestamp resolver (YAML 1.1 would turn 2026-11-25 into datetime.date).
for _ch, _resolvers in list(DateAsStringLoader.yaml_implicit_resolvers.items()):
    DateAsStringLoader.yaml_implicit_resolvers[_ch] = [
        (tag, regexp) for tag, regexp in _resolvers if tag != "tag:yaml.org,2002:timestamp"
    ]

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit("jsonschema is required. pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "cards.schema.json"
FEES_SCHEMA_PATH = ROOT / "schemas" / "fees.schema.json"
CARDS_DIR = ROOT / "cards"
FEES_DIR = ROOT / "fees"
STALE_DAYS_DEFAULT = 60


def parse_args():
    p = argparse.ArgumentParser(description="Validate card files and airline fee snapshots.")
    p.add_argument("--stale-days", type=int, default=STALE_DAYS_DEFAULT)
    p.add_argument("--strict", action="store_true", help="Exit 2 if any last_checked is stale")
    p.add_argument("files", nargs="*", help="Specific YAML files (default: cards/*.yaml)")
    return p.parse_args()


def load_yaml(path: Path):
    with path.open() as f:
        return yaml.load(f, Loader=DateAsStringLoader)


def iter_dates(doc):
    """Yield (label, YYYY-MM-DD) for every last_checked in the file."""
    if doc.get("table_last_checked"):
        yield "table_last_checked", str(doc["table_last_checked"])
    for pid, prog in (doc.get("programs") or {}).items():
        for i, partner in enumerate(prog.get("partners") or []):
            if "last_checked" in partner:
                yield f"programs.{pid}.partners[{i}].{partner.get('name','?')}", str(partner["last_checked"])
    for card in doc.get("cards") or []:
        if "last_checked" in card:
            yield f"cards.{card.get('id','?')}", str(card["last_checked"])


def check_date(label, raw, today, stale_days):
    """Return (error_line or None, warning_line or None)."""
    try:
        checked = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return f"  ERROR: {label}: last_checked {raw!r} is not YYYY-MM-DD", None
    age = (today - checked).days
    if age > stale_days:
        return None, f"  WARN: {label}: last_checked {raw} is {age} days old (threshold {stale_days})"
    return None, None


def validate_fees(today, stale_days):
    """Validate fees/*.yaml. Missing snapshots are allowed; a broken one is not."""
    import json
    files = sorted(FEES_DIR.glob("*.yaml")) if FEES_DIR.is_dir() else []
    if not files:
        print("== fees/")
        print("  no snapshots (optional)")
        return 0, 0
    schema = json.loads(FEES_SCHEMA_PATH.read_text())
    validator = Draft202012Validator(schema)
    errors = 0
    warnings = 0
    for path in files:
        print(f"== {path.relative_to(ROOT)}")
        try:
            doc = load_yaml(path)
        except Exception as e:
            print(f"  ERROR: could not parse YAML: {e}")
            errors += 1
            continue
        if not isinstance(doc, dict):
            print("  ERROR: file did not parse to a mapping")
            errors += 1
            continue
        schema_errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        for e in schema_errs:
            loc = ".".join(str(p) for p in e.path) or "(root)"
            print(f"  ERROR: {loc}: {e.message}")
            errors += 1
        source = doc.get("source_url") or ""
        if doc.get("verified") and not source.startswith("https://"):
            print("  ERROR: verified:true but source_url is not an https URL")
            errors += 1
        if doc.get("last_checked"):
            err, warn = check_date("last_checked", str(doc["last_checked"]), today, stale_days)
            if err:
                print(err)
                errors += 1
            if warn:
                print(warn)
                warnings += 1
        if not schema_errs:
            print(f"  {len(doc.get('fare_brands') or [])} fare brands")
    return errors, warnings


def main():
    args = parse_args()
    files = [Path(f) for f in args.files] if args.files else sorted(CARDS_DIR.glob("*.yaml"))
    if not files:
        print("No card files found.", file=sys.stderr)
        return 1

    import json
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = Draft202012Validator(schema)

    errors = 0
    warnings = 0
    today = date.today()

    for path in files:
        print(f"== {path.relative_to(ROOT) if path.is_absolute() and ROOT in path.parents else path}")
        try:
            doc = load_yaml(path)
        except Exception as e:
            print(f"  ERROR: could not parse YAML: {e}")
            errors += 1
            continue
        if not isinstance(doc, dict):
            print("  ERROR: file did not parse to a mapping")
            errors += 1
            continue

        schema_errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        for e in schema_errs:
            loc = ".".join(str(p) for p in e.path) or "(root)"
            print(f"  ERROR: {loc}: {e.message}")
            errors += 1

        # Program references
        programs = set((doc.get("programs") or {}).keys())
        for card in doc.get("cards") or []:
            if card.get("program") and card["program"] not in programs:
                print(f"  ERROR: cards.{card.get('id')}: program {card['program']!r} is not in programs")
                errors += 1

        # Official-source rule for verified:true partners: need a URL somewhere
        for pid, prog in (doc.get("programs") or {}).items():
            shared = prog.get("partners_source_url") or ""
            for partner in prog.get("partners") or []:
                if partner.get("verified") and not (partner.get("source_url") or shared or (prog.get("general_sources") or [])):
                    print(f"  ERROR: {pid}/{partner.get('name')}: verified:true but no source_url")
                    errors += 1

        for label, raw in iter_dates(doc):
            err, warn = check_date(label, raw, today, args.stale_days)
            if err:
                print(err)
                errors += 1
            if warn:
                print(warn)
                warnings += 1

        if not schema_errs:
            n_cards = len(doc.get("cards") or [])
            n_partners = sum(len(p.get("partners") or []) for p in (doc.get("programs") or {}).values())
            print(f"  {n_cards} cards, {n_partners} partners")

    fee_errors, fee_warnings = validate_fees(today, args.stale_days)
    errors += fee_errors
    warnings += fee_warnings

    print()
    print(f"{errors} error(s), {warnings} stale-date warning(s)")
    if errors:
        return 1
    if warnings and args.strict:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
