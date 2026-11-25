#!/usr/bin/env python3
"""Read Google Flights price history from a search response, and a local log.

The free fast-flights scraper does not return a price-insight object. The HTML
it downloads does: a "Prices are currently low/typical/high" sentence, and a
daily [timestamp, price] series inside the same script.ds:1 JSON the parser
already reads. This module extracts that. It does not call a paid API and it
does not invent points.

Every search.py run also appends one line to a local JSONL file (default
~/.flight-points-optimiser/history.jsonl, or $FLIGHT_POINTS_HISTORY). That log
is a supplement. On the first run it only holds this search; the Google series
is what provides history from day one, when Google included it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import inputs

LEVEL_RE = re.compile(
    r"Prices are currently(?:\s|<[^>]+>)*(low|typical|high)\b",
    re.IGNORECASE,
)
ICON_RE = re.compile(r"ic_price_(low|typical|high)(?:_|\.)", re.IGNORECASE)
DAY_MS = 86400000

RANGE_NOTE = (
    "range_low and range_high are the lower and upper figures in the same "
    "Google Flights insight block as the history graph (the current graph "
    "price sits in that block). The initial HTML does not print them as a "
    "sentence; the low/typical/high word is a separate sentence. On the "
    "LHR-JFK samples checked while building this, the word was 'typical' and "
    "the latest graph price sat inside this pair."
)


def default_history_path() -> Path:
    env = os.environ.get("FLIGHT_POINTS_HISTORY")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".flight-points-optimiser" / "history.jsonl"


def _payload(html: str):
    """Return the script.ds:1 JSON list, or None if this page has no flight payload."""
    marker = 'class="ds:1"'
    # selectolax is optional here so a tiny fixture still parses if the class is present.
    start = html.find(marker)
    if start < 0:
        start = html.find("script")
    # Prefer the same split fast-flights uses, limited to the ds:1 script when found.
    chunk = html
    if 'class="ds:1"' in html:
        i = html.find('class="ds:1"')
        chunk = html[i:i + 500000]
    if "data:" not in chunk:
        return None
    data = chunk.split("data:", 1)[1].rsplit(",", 1)[0].strip()
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list):
        return None
    return payload


def _is_point(item) -> bool:
    return (
        isinstance(item, list)
        and len(item) >= 2
        and isinstance(item[0], (int, float))
        and item[0] > 10**12
        and isinstance(item[1], (int, float))
        and not isinstance(item[1], bool)
    )


def _series_ok(series: list) -> bool:
    if len(series) < 7 or not all(_is_point(p) for p in series):
        return False
    times = [int(p[0]) for p in series]
    ordered = times == sorted(times) or times == sorted(times, reverse=True)
    if not ordered:
        return False
    steps = [abs(times[i + 1] - times[i]) for i in range(len(times) - 1)]
    daily = sum(1 for s in steps if 20 * 3600 * 1000 <= s <= 28 * 3600 * 1000)
    return daily >= len(steps) * 0.8


def _find_insight_block(payload):
    """Find the list that holds the daily series and the neighbouring price fields.

    The walk is bounded so a hostile page cannot recurse until the interpreter stops.
    """
    found = []
    stack = [payload]
    while stack:
        node = stack.pop()
        if not isinstance(node, list):
            continue
        if _series_ok(node):
            found.append(("series", node))
        # Parent shaped like the live payload: index 10 is [series].
        if (
            len(node) > 10
            and isinstance(node[10], list)
            and node[10]
            and _series_ok(node[10][0] if isinstance(node[10][0], list) else [])
        ):
            found.append(("block", node))
        for child in reversed(node):
            if isinstance(child, list):
                stack.append(child)
    blocks = [n for kind, n in found if kind == "block"]
    if blocks:
        return blocks[0]
    return None


def _level(html: str):
    m = LEVEL_RE.search(html)
    if m:
        return m.group(1).lower()
    m = ICON_RE.search(html)
    if m:
        return m.group(1).lower()
    return None


def _utc_date(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).date().isoformat()


def extract_price_insight(html: str) -> dict:
    """Pull Google's price level and history graph out of one search response.

    Returns an empty history when the page has no graph. Never fills gaps.
    """
    level = _level(html or "")
    out = {
        "source": "Google Flights search HTML parsed locally (fast-flights, no paid API)",
        "price_level": level,
        "level_source": (
            "The sentence 'Prices are currently low/typical/high' in that HTML"
            if level
            else None
        ),
        "insight_price": None,
        "range_low": None,
        "range_high": None,
        "range_note": None,
        "history": [],
        "history_points": 0,
        "history_note": None,
    }
    payload = _payload(html or "")
    block = _find_insight_block(payload) if payload is not None else None
    if block is None:
        out["history_note"] = (
            "No daily price-history graph was in this response. "
            "fast-flights' parsed flight list does not include one either. "
            "Do not invent past prices. Open the same Google Flights search "
            "and read the Price insights / Price history panel, or try the search again."
        )
        return out
    raw = block[10][0]
    raw = sorted(raw, key=lambda p: p[0])
    history = [
        {"date": _utc_date(int(ms)), "price": int(price), "at_ms": int(ms)}
        for ms, price in ((p[0], p[1]) for p in raw)
    ]
    out["history"] = history
    out["history_points"] = len(history)
    out["history_note"] = (
        "Daily prices from the graph embedded in the Google Flights search "
        "response (script.ds:1). Dates are the graph timestamps in UTC, which "
        "can sit one calendar day off a market's local date. This is the "
        "history of the insight price for the searched dates, not a forecast."
    )
    last = history[-1]["price"]
    insight_price = last
    if isinstance(block[1], list) and len(block[1]) >= 2 and isinstance(block[1][1], (int, float)):
        insight_price = int(block[1][1])
    out["insight_price"] = insight_price
    low = high = None
    if len(block) > 5 and isinstance(block[2], list) and isinstance(block[5], list):
        if isinstance(block[2][1] if len(block[2]) > 1 else None, (int, float)) and isinstance(
            block[5][1] if len(block[5]) > 1 else None, (int, float)
        ):
            low, high = int(block[2][1]), int(block[5][1])
    if low is not None and high is not None and low <= high:
        out["range_low"] = low
        out["range_high"] = high
        out["range_note"] = RANGE_NOTE
    return out


def percentile_rank(value: float, samples: list) -> float:
    """Percent of the sample at or below value, with ties counted halfway. 0-100."""
    if not samples:
        raise ValueError("empty sample")
    below = sum(1 for s in samples if s < value)
    equal = sum(1 for s in samples if s == value)
    return 100.0 * (below + 0.5 * equal) / len(samples)


def band_from_percentile(pct: float) -> str:
    """Our label from the graph, not Google's word. Stated as a definition."""
    if pct <= 35:
        return "low"
    if pct >= 70:
        return "high"
    return "typical"


def _median(values: list):
    return statistics.median(values) if values else None


def graph_stats(history: list) -> dict:
    prices = [int(p["price"]) for p in history]
    if not prices:
        return {"points": 0}
    latest = prices[-1]
    pct = percentile_rank(latest, prices)
    trend = None
    if len(prices) >= 14:
        earlier = _median(prices[:7])
        later = _median(prices[-7:])
        if earlier:
            change = (later - earlier) / earlier
            if abs(change) < 0.03:
                direction = "flat"
            elif change > 0:
                direction = "up"
            else:
                direction = "down"
            trend = {
                "direction": direction,
                "earlier_median": earlier,
                "later_median": later,
                "change_ratio": round(change, 4),
                "note": "Median of the first 7 graph points versus the latest 7. Descriptive, not a forecast.",
            }
    return {
        "points": len(prices),
        "first_date": history[0]["date"],
        "last_date": history[-1]["date"],
        "min": min(prices),
        "median": _median(prices),
        "max": max(prices),
        "latest": latest,
        "latest_percentile": round(pct, 1),
        "our_band": band_from_percentile(pct),
        "our_band_note": "low means the latest point is at or below the 35th percentile of this graph; high means at or above the 70th. This is not Google's label.",
        "trend": trend,
    }


def key_of(rec: dict) -> tuple:
    return (
        rec.get("origin"),
        rec.get("destination"),
        rec.get("depart_date"),
        rec.get("return_date"),
        rec.get("cabin"),
        int(rec.get("adults") or 1),
        int(rec.get("children") or 0),
        rec.get("currency") or "",
    )


def record_observation(rec: dict, path: Path | None = None) -> Path:
    path = inputs.prepare_data_file(path or default_history_path(), (".jsonl",))
    line = json.dumps(inputs.sanitize_observation(rec), ensure_ascii=False, separators=(",", ":"))
    inputs.append_private(path, line + "\n")
    return path


def load_observations(path: Path | None = None) -> list:
    path = inputs.normalize_data_path(path or default_history_path(), (".jsonl",))
    if not path.is_file():
        return []
    if path.is_symlink() or path.stat().st_size > 8_000_000:
        raise ValueError("history file is a symlink or larger than 8MB")
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if len(line) > 100_000:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(rows) >= 10000:
                break
    return rows


def summarize(match: dict, path: Path | None = None) -> dict:
    """Stats for one route and date pair from the local log and any stored Google graph."""
    wanted = key_of(match)
    rows = [r for r in load_observations(path) if key_of(r) == wanted]
    prices = [r["price"] for r in rows if isinstance(r.get("price"), (int, float))]
    graph = []
    level = None
    range_low = range_high = None
    insight_price = None
    for r in reversed(rows):
        if r.get("google_history"):
            graph = r["google_history"]
            level = r.get("google_price_level")
            range_low = r.get("google_range_low")
            range_high = r.get("google_range_high")
            insight_price = r.get("google_insight_price")
            break
    local = {}
    if prices:
        latest = prices[-1]
        local = {
            "observations": len(prices),
            "min": min(prices),
            "median": _median(prices),
            "max": max(prices),
            "latest": latest,
            "latest_percentile": round(percentile_rank(latest, prices), 1),
            "our_band": band_from_percentile(percentile_rank(latest, prices)),
            "first_seen": rows[0].get("fetched_at"),
            "last_seen": rows[-1].get("fetched_at"),
        }
    return {
        "key": {
            "origin": wanted[0],
            "destination": wanted[1],
            "depart_date": wanted[2],
            "return_date": wanted[3],
            "cabin": wanted[4],
            "adults": wanted[5],
            "children": wanted[6],
            "currency": wanted[7],
        },
        "local_log": local or {"observations": 0, "note": "No saved searches for this route and date pair yet."},
        "google_graph": graph_stats(graph) if graph else {
            "points": 0,
            "note": "No Google price-history graph stored for this search. The local log does not invent one.",
        },
        "google_price_level": level,
        "google_insight_price": insight_price,
        "google_range_low": range_low,
        "google_range_high": range_high,
    }


def format_summary(summary: dict) -> str:
    k = summary["key"]
    ret = k["return_date"] or "one-way"
    cur = k["currency"] or "Google's currency"
    lines = [
        "Price history for %s-%s departing %s returning %s, %s, %s adult(s), %s child(ren), %s."
        % (k["origin"], k["destination"], k["depart_date"], ret, k["cabin"], k["adults"], k["children"], cur),
        "Not a forecast.",
    ]
    g = summary["google_graph"]
    if g.get("points"):
        lines.append(
            "Google graph: %d daily points, %s to %s (UTC dates). min %s, median %s, max %s. Latest %s is at the %s percentile of this graph (%s by our cut: <=35 low, >=70 high)."
            % (g["points"], g["first_date"], g["last_date"], g["min"], g["median"], g["max"], g["latest"], g["latest_percentile"], g["our_band"])
        )
        if g.get("trend"):
            t = g["trend"]
            lines.append(
                "Graph trend: %s (first-7 median %s, latest-7 median %s, change %s). %s"
                % (t["direction"], t["earlier_median"], t["later_median"], t["change_ratio"], t["note"])
            )
    else:
        lines.append(g.get("note", "No Google graph."))
    if summary.get("google_price_level"):
        lines.append(
            "Google's own label on the page: prices are currently %s. That word is separate from our percentile."
            % summary["google_price_level"]
        )
    if summary.get("google_range_low") is not None:
        lines.append(
            "Insight block bounds: %s-%s %s. %s" % (summary["google_range_low"], summary["google_range_high"], cur, RANGE_NOTE)
        )
    loc = summary["local_log"]
    if loc.get("observations"):
        lines.append(
            "Local log: %d observation(s), min %s, median %s, max %s, latest %s (%s percentile of the log)."
            % (loc["observations"], loc["min"], loc["median"], loc["max"], loc["latest"], loc["latest_percentile"])
        )
    else:
        lines.append(loc.get("note", "No local observations."))
    lines.append("This is not a guaranteed forecast. Do not invent prices that are not listed above.")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="Show stored and Google-graph price history for one route and date pair.")
    p.add_argument("origin", nargs="?", help="IATA origin")
    p.add_argument("dest", nargs="?", help="IATA destination")
    p.add_argument("date", nargs="?", help="Departure YYYY-MM-DD")
    p.add_argument("--return", dest="ret", help="Return YYYY-MM-DD")
    p.add_argument("--cabin", default="economy")
    p.add_argument("--adults", type=int, default=1)
    p.add_argument("--children", type=int, default=0)
    p.add_argument("--currency", default="")
    p.add_argument("--history", help="JSONL path (default ~/.flight-points-optimiser/history.jsonl or $FLIGHT_POINTS_HISTORY)")
    p.add_argument("--from-html", help="Parse a saved Google Flights HTML response instead of the log")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        path = inputs.normalize_data_path(a.history, (".jsonl",)) if a.history else default_history_path()
    except ValueError as exc:
        p.error(str(exc))
    if a.from_html:
        try:
            html_path = inputs.normalize_data_path(a.from_html, (".html", ".htm", ".txt"))
        except ValueError as exc:
            p.error(str(exc))
        if not html_path.is_file() or html_path.is_symlink():
            p.error("HTML file is missing or is a symlink")
        if html_path.stat().st_size > 2_000_000:
            p.error("HTML file is larger than 2MB")
        html = html_path.read_text(encoding="utf-8", errors="replace")
        insight = extract_price_insight(html)
        text = json.dumps({k: v for k, v in insight.items() if k != "history"}, indent=2)
        stats = graph_stats(insight["history"])
        print(text)
        print(json.dumps(stats, indent=2))
        print("history_points", insight["history_points"])
        if insight["history"]:
            print("first", insight["history"][0])
            print("last", insight["history"][-1])
        return 0
    if not (a.origin and a.dest and a.date):
        p.error("origin, dest, and date are required unless --from-html is set")
    origin = inputs.iata(a.origin, "origin", p)
    dest = inputs.iata(a.dest, "destination", p)
    depart = inputs.iso_date(a.date, "departure date", p).isoformat()
    ret = inputs.iso_date(a.ret, "return date", p).isoformat() if a.ret else None
    summary = summarize(
        {
            "origin": origin,
            "destination": dest,
            "depart_date": depart,
            "return_date": ret,
            "cabin": inputs.cabin(a.cabin, p),
            "adults": inputs.bounded_int(a.adults, "--adults", p, 1, 9),
            "children": inputs.bounded_int(a.children, "--children", p, 0, 9),
            "currency": inputs.currency(a.currency, p),
        },
        path,
    )
    if a.json:
        print(json.dumps(summary, indent=2))
    else:
        print(format_summary(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
