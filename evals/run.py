#!/usr/bin/env python3
"""Print the eval prompts and check that the file is well formed.

This does not call a model. A person runs the prompts and ticks evals/SCORE.md
before a release. `python evals/run.py --check` is safe for CI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required. pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parents[1]
CASES = Path(__file__).resolve().parent / "cases.yaml"
REQUIRED = ("id", "kind", "prompt", "must")


class NoAliasLoader(yaml.SafeLoader):
    def ignore_aliases(self, _data):
        return True


def load():
    doc = yaml.load(CASES.read_text(), Loader=NoAliasLoader)
    if not isinstance(doc, dict) or not isinstance(doc.get("cases"), list):
        raise SystemExit("evals/cases.yaml needs a cases list")
    ids = []
    for case in doc["cases"]:
        for key in REQUIRED:
            if not case.get(key):
                raise SystemExit(f"case missing {key}: {case!r}")
        if case["id"] in ids:
            raise SystemExit("duplicate id " + case["id"])
        ids.append(case["id"])
    n = len(doc["cases"])
    if not 10 <= n <= 20:
        raise SystemExit(f"expected 10 to 20 cases, found {n}")
    return doc


def main(argv=None):
    p = argparse.ArgumentParser(description="Show eval prompts. Does not score a model.")
    p.add_argument("--check", action="store_true", help="Validate the file and exit")
    a = p.parse_args(argv)
    doc = load()
    if a.check:
        print(f"{len(doc['cases'])} eval cases ok")
        return 0
    print("Shared rules:")
    for line in doc.get("shared_must") or []:
        print("  [ ] " + line)
    for line in doc.get("shared_must_not") or []:
        print("  [ ] does not: " + line)
    print()
    for i, case in enumerate(doc["cases"], 1):
        print(f"## {i}. {case['id']} ({case['kind']})")
        print(case["prompt"].strip())
        print("Expect:")
        for line in case["must"]:
            print("  [ ] " + line)
        print()
    print("Record pass or fail in evals/SCORE.md. Do not invent a score.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
