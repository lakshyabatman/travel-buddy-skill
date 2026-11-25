#!/usr/bin/env python3
"""Cron-friendly price watcher. Never books, pays, or transfers points.

Re-runs search.py (which appends to the local price history) and compares the
cheapest fare with a small state file. Exit codes:

  0  checked, nothing new (or the departure date has passed)
  2  alert: a new low, or a fare at or below --threshold not already alerted
  1  the search failed or returned no fare

The first successful check stores a baseline and does not alert, unless
--threshold is set and the fare is already at or below it.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import inputs

ROOT = Path(__file__).resolve().parent
SEARCH_TIMEOUT_S = 300


def state_path(origin, dest, depart, explicit):
    if explicit:
        path = inputs.normalize_data_path(explicit, (".json",))
        if not path.name.startswith("watch"):
            raise ValueError("state file name must start with watch")
        return path
    origin = inputs.iata(origin, "origin")
    dest = inputs.iata(dest, "destination")
    depart = inputs.iso_date(depart, "departure date").isoformat()
    return inputs.normalize_data_path(
        Path.home() / ".flight-points-optimiser" / ("watch-%s-%s-%s.json" % (origin, dest, depart)),
        (".json",),
    )


def decide(previous_lowest, last_alert_price, price, threshold):
    """Return (alert, reason). previous_lowest None means this is the baseline."""
    if previous_lowest is None:
        if threshold is not None and price <= threshold:
            return True, "baseline is at or below the threshold"
        return False, "baseline recorded"
    if price < previous_lowest:
        return True, "new low"
    if threshold is not None and price <= threshold and price != last_alert_price:
        return True, "at or below the threshold"
    return False, "no new low"


def cheapest(payload):
    rows = payload.get("results") or []
    priced = [r for r in rows if isinstance(r.get("price"), (int, float))]
    if not priced:
        return None
    return min(priced, key=lambda r: (r["price"], r.get("stops") or 0))


def load_state(path: Path):
    if not path.is_file() or path.is_symlink():
        return {}
    if path.stat().st_size > 1_000_000:
        raise ValueError("state file is larger than 1MB")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def main(argv=None):
    p = argparse.ArgumentParser(description="Re-check a fare and alert on a new low. Never books.")
    p.add_argument("origin")
    p.add_argument("dest")
    p.add_argument("date", help="Departure YYYY-MM-DD")
    p.add_argument("--return", dest="ret")
    p.add_argument("--cabin", default="economy")
    p.add_argument("--adults", type=int, default=1)
    p.add_argument("--children", type=int, default=0)
    p.add_argument("--currency", default="")
    p.add_argument("--flex", type=int, default=0)
    p.add_argument("--threshold", type=float, default=None, help="Alert when the fare is at or below this number")
    p.add_argument("--state", help="State JSON path")
    p.add_argument("--history", help="Passed through to search.py")
    a = p.parse_args(argv)

    try:
        origin = inputs.iata(a.origin, "origin")
        dest = inputs.iata(a.dest, "destination")
        depart = inputs.iso_date(a.date, "departure date")
        ret = inputs.iso_date(a.ret, "return date").isoformat() if a.ret else None
        cabin = inputs.cabin(a.cabin)
        adults = inputs.bounded_int(a.adults, "--adults", None, 1, 9)
        children = inputs.bounded_int(a.children, "--children", None, 0, 9)
        flex = inputs.bounded_int(a.flex, "--flex", None, 0, 7)
        cur = inputs.currency(a.currency)
        if a.threshold is not None and not math.isfinite(a.threshold):
            raise ValueError("threshold must be a finite number")
        if a.history:
            inputs.normalize_data_path(a.history, (".jsonl",))
        path = state_path(origin, dest, depart.isoformat(), a.state)
    except ValueError as exc:
        print(inputs.one_line(exc), file=sys.stderr)
        return 1
    if depart < date.today():
        print("STOP departure date %s has passed. No search, no booking." % depart.isoformat())
        return 0

    cmd = [sys.executable, str(ROOT / "search.py"), origin, dest, depart.isoformat(), "--json-only", "--top", "5",
           "--cabin", cabin, "--adults", str(adults), "--children", str(children), "--flex", str(flex)]
    if ret:
        cmd += ["--return", ret]
    if cur:
        cmd += ["--currency", cur]
    if a.history:
        cmd += ["--history", a.history]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=SEARCH_TIMEOUT_S, shell=False)
    except subprocess.TimeoutExpired:
        print("search timed out", file=sys.stderr)
        return 1
    if proc.returncode not in (0, 2):
        err = proc.stderr or proc.stdout or "search failed"
        print(inputs.one_line(err), file=sys.stderr)
        return 1
    if len(proc.stdout) > 5_000_000:
        print("search output was too large", file=sys.stderr)
        return 1
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("search.py did not return JSON", file=sys.stderr)
        return 1
    row = cheapest(payload)
    if row is None:
        print("No fare returned. Not treated as a price drop.", file=sys.stderr)
        return 1

    try:
        state = load_state(path)
    except ValueError as exc:
        print(inputs.one_line(exc), file=sys.stderr)
        return 1
    if state.get("origin") not in (None, origin) or state.get("destination") not in (None, dest):
        print("State file is for a different route; refusing to overwrite.", file=sys.stderr)
        return 1
    prev = (state.get("lowest") or {}).get("price")
    if isinstance(prev, bool) or not isinstance(prev, (int, float)):
        prev = None
    last_alert = state.get("last_alert_price")
    alert, reason = decide(prev, last_alert, row["price"], a.threshold)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    lowest = row["price"] if prev is None else min(prev, row["price"])
    seen_at = now if lowest == row["price"] or prev is None else (state.get("lowest") or {}).get("seen_at", now)
    fresh = {
        "origin": origin,
        "destination": dest,
        "depart_date": depart.isoformat(),
        "return_date": ret,
        "currency": cur,
        "cabin": cabin,
        "adults": adults,
        "children": children,
        "lowest": {"price": lowest, "seen_at": seen_at, "source": "Google Flights via fast-flights"},
        "checks": int(state.get("checks") or 0) + 1,
        "last_checked": now,
        "last_price": row["price"],
    }
    if alert:
        fresh["last_alert_price"] = row["price"]
    elif state.get("last_alert_price") is not None:
        fresh["last_alert_price"] = state.get("last_alert_price")
    try:
        stored = inputs.prepare_data_file(path, (".json",))
        inputs.write_private_text(stored, json.dumps(fresh, indent=2) + "\n")
    except ValueError as exc:
        print("State was not saved: %s" % inputs.one_line(exc), file=sys.stderr)
        return 1

    label = cur or "the currency Google chose"
    if alert:
        print("ALERT %s %s-%s %s: %s %s (%s). Previous low %s. Nothing was booked or transferred." % (
            reason, origin, dest, depart.isoformat(), row["price"], label, prev if prev is not None else "none", prev))
        return 2
    print("OK %s-%s %s: %s %s. Lowest stored %s. No alert." % (origin, dest, depart.isoformat(), row["price"], label, lowest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
