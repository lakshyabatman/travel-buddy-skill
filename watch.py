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
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def state_path(origin, dest, depart, explicit):
    if explicit:
        return Path(explicit).expanduser()
    safe = "%s-%s-%s" % (origin, dest, depart)
    return Path.home() / ".flight-points-optimiser" / ("watch-%s.json" % safe)


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
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


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

    origin, dest = a.origin.upper(), a.dest.upper()
    try:
        depart = date.fromisoformat(a.date)
    except ValueError:
        print("Departure date must be YYYY-MM-DD", file=sys.stderr)
        return 1
    if depart < date.today():
        print("STOP departure date %s has passed. No search, no booking." % a.date)
        return 0

    cmd = [sys.executable, str(ROOT / "search.py"), origin, dest, a.date, "--json-only", "--top", "5",
           "--cabin", a.cabin, "--adults", str(a.adults), "--children", str(a.children), "--flex", str(a.flex)]
    if a.ret:
        cmd += ["--return", a.ret]
    if a.currency:
        cmd += ["--currency", a.currency]
    if a.history:
        cmd += ["--history", a.history]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode not in (0, 2):
        err = (proc.stderr or proc.stdout or "search failed").strip()
        print(err, file=sys.stderr)
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

    path = state_path(origin, dest, a.date, a.state)
    state = load_state(path)
    prev = (state.get("lowest") or {}).get("price")
    last_alert = state.get("last_alert_price")
    alert, reason = decide(prev, last_alert, row["price"], a.threshold)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    lowest = row["price"] if prev is None else min(prev, row["price"])
    state.update({
        "origin": origin,
        "destination": dest,
        "depart_date": a.date,
        "return_date": a.ret,
        "currency": a.currency,
        "cabin": a.cabin,
        "adults": a.adults,
        "children": a.children,
        "lowest": {"price": lowest, "seen_at": now if lowest == row["price"] or prev is None else state.get("lowest", {}).get("seen_at", now), "source": "Google Flights via fast-flights"},
        "checks": int(state.get("checks") or 0) + 1,
        "last_checked": now,
        "last_price": row["price"],
    })
    if alert:
        state["last_alert_price"] = row["price"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")

    cur = a.currency or "the currency Google chose"
    if alert:
        print("ALERT %s %s-%s %s: %s %s (%s). Previous low %s. Nothing was booked or transferred." % (
            reason, origin, dest, a.date, row["price"], cur, prev if prev is not None else "none", prev))
        return 2
    print("OK %s-%s %s: %s %s. Lowest stored %s. No alert." % (origin, dest, a.date, row["price"], cur, lowest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
