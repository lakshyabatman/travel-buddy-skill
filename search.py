#!/usr/bin/env python3
"""Google Flights helper for the flight-points-optimiser skill.

Uses the free, unofficial `fast-flights` library (https://github.com/AWeirdDev/fast-flights),
which scrapes Google Flights. No API key, no paid API. Because it scrapes, it can break
whenever Google changes its page, or get rate-limited. If it fails, fall back to opening
Google Flights / Skyscanner in a browser (the URL of each query is printed with --urls).

Prices are what Google Flights showed at fetch time, in the requested currency, for ALL
passengers combined. For round trips, the listed segments are the OUTBOUND legs and the
price is the round-trip total Google shows for that outbound choice. Always re-check the
fare on the airline/OTA site before booking.

Examples:
  python search.py MEX MAD 2026-12-16 --currency MXN
  python search.py SIN SYD 2027-01-10 --return 2027-01-17 --cabin business --currency AUD
  python search.py GRU LIS 2027-02-05 --flex 3 --currency BRL --top 15
  python search.py NBO CDG 2027-03-01 --json-only > out.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta

import inputs

FETCH_TIMEOUT_S = 20
MAX_HTML_CHARS = 4_000_000


def daterange(center: date, flex: int):
    for d in range(-flex, flex + 1):
        yield center + timedelta(days=d)


def hhmm(t) -> str:
    return "%02d:%02d" % (t[0], t[1])


def fmt_dur(mins: int) -> str:
    return "%dh%02dm" % divmod(int(mins), 60)


def _load_flights():
    try:
        from fast_flights import FlightQuery, Passengers, create_query
        from fast_flights.parser import parse as parse_flights
        try:
            from fast_flights import FlightsNotFound
        except ImportError:  # older versions
            FlightsNotFound = Exception  # type: ignore
    except ImportError as exc:  # pragma: no cover
        sys.exit(
            "fast-flights is not installed (or a dependency is missing): %s\n"
            "Run: pip install -r requirements.txt" % inputs.public_error(exc)
        )
    return FlightQuery, Passengers, create_query, parse_flights, FlightsNotFound


def _fetch_html(query) -> str:
    """Fetch with an explicit timeout. primp does not use Python's socket timeout."""
    import fast_flights.fetcher as fetcher
    from primp import Client as PrimpClient

    def client_with_timeout(*args, **kwargs):
        kwargs.setdefault("timeout", FETCH_TIMEOUT_S)
        kwargs.setdefault("connect_timeout", 10)
        kwargs.setdefault("read_timeout", FETCH_TIMEOUT_S)
        return PrimpClient(*args, **kwargs)

    previous = fetcher.Client
    fetcher.Client = client_with_timeout
    try:
        html = fetcher.fetch_flights_html(query)
    finally:
        fetcher.Client = previous
    if not isinstance(html, str):
        raise RuntimeError("flight response was not text")
    if len(html) > MAX_HTML_CHARS:
        raise RuntimeError("flight response exceeded %d characters" % MAX_HTML_CHARS)
    return html


def run_query(origin, dest, dep, ret, cabin, adults, children, currency, max_stops):
    FlightQuery, Passengers, create_query, parse_flights, FlightsNotFound = _load_flights()
    flights = [FlightQuery(date=dep.isoformat(), from_airport=origin, to_airport=dest)]
    if ret:
        flights.append(FlightQuery(date=ret.isoformat(), from_airport=dest, to_airport=origin))
    q = create_query(
        flights=flights,
        seat=cabin,
        trip="round-trip" if ret else "one-way",
        passengers=Passengers(adults=adults, children=children),
        currency=currency,
        language="en",
        max_stops=max_stops,
    )
    rows = []
    insight = None
    try:
        html = _fetch_html(q)
    except Exception as e:
        raise RuntimeError(inputs.public_error(e)) from e
    try:
        results = parse_flights(html)
    except FlightsNotFound:
        results = []
    try:
        import history
        insight = history.extract_price_insight(html)
    except Exception as e:
        insight = {"history_points": 0, "history_note": "Could not read a price graph: %s" % inputs.public_error(e)}
    for f in results:
        segs = f.flights
        if not segs:
            continue
        first, last = segs[0], segs[-1]
        # Total elapsed time incl. layovers, from departure/arrival wall clock (local times;
        # approximate across time zones, so we also keep the sum of flying minutes).
        fly = sum(int(s.duration or 0) for s in segs)
        rows.append(
            {
                "origin": origin,
                "destination": dest,
                "depart_date": dep.isoformat(),
                "return_date": ret.isoformat() if ret else None,
                "price": f.price,
                "currency": currency,
                "airlines": f.airlines,
                "stops": len(segs) - 1,
                "route": "-".join([segs[0].from_airport.code] + [s.to_airport.code for s in segs]),
                "depart_time": hhmm(first.departure.time),
                "arrive_time": hhmm(last.arrival.time),
                "arrive_date": "%04d-%02d-%02d" % tuple(last.arrival.date),
                "flying_minutes": fly,
                "segments": [
                    {
                        "from": s.from_airport.code,
                        "to": s.to_airport.code,
                        "dep": "%04d-%02d-%02d %s" % (*s.departure.date, hhmm(s.departure.time)),
                        "arr": "%04d-%02d-%02d %s" % (*s.arrival.date, hhmm(s.arrival.time)),
                        "minutes": s.duration,
                        "aircraft": s.plane_type,
                    }
                    for s in segs
                ],
                "google_flights_url": q.url(),
                "source": "Google Flights via fast-flights",
                "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
        )
    return rows, q.url(), insight


def _save_history(origin, dest, dep, ret, args, rows, insight):
    """Append the cheapest fare and any Google graph. Failure must not fail the search."""
    try:
        import history
        from pathlib import Path
        cheapest = min(rows, key=_sort_key)
        if not isinstance(cheapest.get("price"), (int, float)) or isinstance(cheapest.get("price"), bool):
            return
        insight = insight or {}
        history.record_observation(
            {
                "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "origin": origin,
                "destination": dest,
                "depart_date": dep.isoformat(),
                "return_date": ret.isoformat() if ret else None,
                "cabin": args.cabin,
                "adults": args.adults,
                "children": args.children,
                "currency": args.currency or "",
                "price": cheapest["price"],
                "source": "Google Flights via fast-flights",
                "google_price_level": insight.get("price_level"),
                "google_insight_price": insight.get("insight_price"),
                "google_range_low": insight.get("range_low"),
                "google_range_high": insight.get("range_high"),
                "google_history": insight.get("history") or [],
            },
            Path(args.history).expanduser() if args.history else None,
        )
    except Exception as e:
        print("Price history was not saved: %s" % inputs.public_error(e), file=sys.stderr)


def _sort_key(row):
    price = row.get("price")
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        price = 10**12
    stops = row.get("stops") if isinstance(row.get("stops"), int) else 99
    fly = row.get("flying_minutes") if isinstance(row.get("flying_minutes"), int) else 10**9
    return (price, stops, fly)


def _fmt_price(price) -> str:
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        return "?"
    return "{:,}".format(price)


def main(argv=None):
    p = argparse.ArgumentParser(description="Cheapest-fare scan on Google Flights (via fast-flights).")
    p.add_argument("origin", help="IATA code, e.g. LIS (see also --airports)")
    p.add_argument("dest", help="IATA code, e.g. GRU")
    p.add_argument("date", help="Departure date YYYY-MM-DD")
    p.add_argument("--return", dest="ret", help="Return date YYYY-MM-DD (round trip)")
    p.add_argument("--cabin", default="economy", choices=sorted(inputs.CABINS))
    p.add_argument("--adults", type=int, default=1)
    p.add_argument("--children", type=int, default=0)
    p.add_argument("--currency", default="", help="ISO 4217 code passed through to Google Flights (USD, EUR, GBP, MXN, BRL, AUD, JPY, ...). Default: empty, so Google chooses. fast-flights supports this.")
    p.add_argument("--max-stops", type=int, default=None)
    p.add_argument("--flex", type=int, default=0, help="Scan +/-N days around the departure date (return shifts by the same amount)")
    p.add_argument("--airports", help="Comma-separated origin airports to compare, e.g. LIS,OPO (overrides origin)")
    p.add_argument("--top", type=int, default=20, help="Rows to print in the table")
    p.add_argument("--delay", type=float, default=1.5, help="Seconds between requests (be polite; avoids blocks)")
    p.add_argument("--json-only", action="store_true", help="Print only JSON (for agents/scripts)")
    p.add_argument("--urls", action="store_true", help="Print the Google Flights URL of each query")
    p.add_argument("--history", help="JSONL file for price history (default ~/.flight-points-optimiser/history.jsonl)")
    p.add_argument("--no-history", action="store_true", help="Do not append this run to the local price history")
    a = p.parse_args(argv)

    origins = inputs.airports(a.airports or a.origin, p)
    dest = inputs.iata(a.dest, "destination", p)
    dep0 = inputs.iso_date(a.date, "departure date", p)
    ret0 = inputs.iso_date(a.ret, "return date", p) if a.ret else None
    if ret0 and ret0 < dep0:
        p.error("--return must be on or after the departure date")
    a.currency = inputs.currency(a.currency, p)
    a.adults = inputs.bounded_int(a.adults, "--adults", p, 1, 9)
    a.children = inputs.bounded_int(a.children, "--children", p, 0, 9)
    if a.max_stops is not None:
        a.max_stops = inputs.bounded_int(a.max_stops, "--max-stops", p, 0, 5)
    a.flex = inputs.bounded_int(a.flex, "--flex", p, 0, 7)
    a.top = inputs.bounded_int(a.top, "--top", p, 1, 50)
    a.delay = inputs.delay_seconds(a.delay, p)
    if a.history:
        try:
            inputs.normalize_data_path(a.history, (".jsonl",))
        except ValueError as exc:
            p.error(str(exc))

    all_rows, errors, urls, insights = [], [], [], []
    for o in origins:
        for dep in daterange(dep0, a.flex):
            if dep < date.today():
                continue
            ret = ret0 + (dep - dep0) if ret0 else None
            try:
                rows, url, insight = run_query(o, dest, dep, ret, a.cabin, a.adults, a.children, a.currency, a.max_stops)
                all_rows.extend(rows)
                urls.append(url)
                insights.append({"origin": o, "depart_date": dep.isoformat(), "return_date": ret.isoformat() if ret else None, "insight": insight})
                if rows and not a.no_history:
                    _save_history(o, dest, dep, ret, a, rows, insight)
            except Exception as e:  # network block, parser break, etc.
                errors.append({"origin": o, "date": dep.isoformat(), "error": inputs.public_error(e)})
            time.sleep(a.delay)

    all_rows.sort(key=_sort_key)
    # Cheapest per date/origin: a quick calendar view
    cal = {}
    for r in all_rows:
        k = (r["origin"], r["depart_date"])
        if k not in cal or _sort_key(r) < _sort_key(cal[k]):
            cal[k] = r
    out = {
        "query": {
            "origins": origins, "destination": dest, "date": a.date, "return": a.ret,
            "cabin": a.cabin, "adults": a.adults, "children": a.children,
            "currency": a.currency, "flex_days": a.flex,
        },
        "cheapest_by_origin_and_date": [
            {"origin": k[0], "depart_date": k[1], "price": v["price"], "airlines": v["airlines"], "stops": v["stops"]}
            for k, v in sorted(cal.items(), key=lambda kv: kv[1]["price"])
        ],
        "results": all_rows,
        "price_insights": [
            {
                "origin": item["origin"],
                "depart_date": item["depart_date"],
                "return_date": item["return_date"],
                "price_level": (item["insight"] or {}).get("price_level"),
                "insight_price": (item["insight"] or {}).get("insight_price"),
                "range_low": (item["insight"] or {}).get("range_low"),
                "range_high": (item["insight"] or {}).get("range_high"),
                "history_points": (item["insight"] or {}).get("history_points"),
                "history_note": (item["insight"] or {}).get("history_note"),
            }
            for item in insights
        ],
        "errors": errors,
    }

    if not a.json_only:
        if all_rows:
            hdr = "%-4s %-10s %10s  %-26s %5s  %-5s %-5s %-8s %s" % (
                "FROM", "DATE", "PRICE", "AIRLINE(S)", "STOPS", "DEP", "ARR", "FLYING", "ROUTE")
            print(hdr)
            print("-" * len(hdr))
            for r in all_rows[: a.top]:
                print("%-4s %-10s %10s  %-26s %5d  %-5s %-5s %-8s %s" % (
                    r["origin"], r["depart_date"], _fmt_price(r["price"]),
                    ", ".join(r["airlines"])[:26], r["stops"], r["depart_time"], r["arrive_time"],
                    fmt_dur(r["flying_minutes"]), r["route"]))
            if len(cal) > 1:
                print("\nCheapest per origin/date:")
                for c in out["cheapest_by_origin_and_date"]:
                    print("  %s %s  %s %s" % (c["origin"], c["depart_date"], a.currency or "?", _fmt_price(c["price"])))
            cur = a.currency or "the currency Google Flights chose"
            print("\nPrices are totals for all passengers in %s as shown by Google Flights at fetch time; re-check before booking." % cur)
            for item in insights:
                ins = item["insight"] or {}
                if ins.get("history_points"):
                    print("Price graph %s %s: %s points, Google label %s, insight price %s, range %s-%s. Not a forecast." % (
                        item["origin"], item["depart_date"], ins.get("history_points"),
                        ins.get("price_level") or "not shown", ins.get("insight_price"),
                        ins.get("range_low"), ins.get("range_high")))
                else:
                    print("No price-history graph for %s %s. Read Price insights on the Google Flights page. Do not invent past prices." % (
                        item["origin"], item["depart_date"]))
        else:
            print("No results. Google may have blocked the request or changed its page; use the browser fallback.", file=sys.stderr)
        if a.urls:
            print("\nGoogle Flights URLs:\n" + "\n".join(urls))
        for e in errors:
            print("ERROR %s %s: %s" % (e["origin"], e["date"], inputs.one_line(e["error"])), file=sys.stderr)
        print("\n--- JSON ---")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if all_rows else 2


if __name__ == "__main__":
    sys.exit(main())
