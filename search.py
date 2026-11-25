#!/usr/bin/env python3
"""Google Flights helper for the flight-points-optimiser skill.

Uses the free, unofficial `fast-flights` library (https://github.com/AWeirdDev/fast-flights),
which scrapes Google Flights. No API key, no paid API. Because it scrapes, it can break
whenever Google changes its page, or get rate-limited. If it fails, fall back to opening
Google Flights / Skyscanner in a browser (the URL of each query is printed with --urls).

Prices are what Google Flights showed at fetch time, in the requested currency, for ALL
passengers combined. For round trips, the listed segments are the OUTBOUND legs and the
price is the round-trip total Google shows for that outbound choice. The return leg is
included only when the parser actually returns it; otherwise the row says "return not
fetched". Elapsed time includes layovers. Always re-check the fare before booking.

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


# Google Flights city codes for a few multi-airport cities. Used only as a fallback when an
# airport code returns an empty or odd payload, and as the hint for --dest-airports.
METROS = {
    "TYO": ("NRT", "HND"),
    "LON": ("LHR", "LGW", "LCY", "STN", "LTN"),
    "NYC": ("JFK", "EWR", "LGA"),
    "PAR": ("CDG", "ORY"),
    "CHI": ("ORD", "MDW"),
    "WAS": ("IAD", "DCA", "BWI"),
    "OSA": ("KIX", "ITM", "UKB"),
    "SEL": ("ICN", "GMP"),
    "BJS": ("PEK", "PKX"),
    "SHA": ("PVG", "SHA"),
    "MIL": ("MXP", "LIN", "BGY"),
    "ROM": ("FCO", "CIA"),
    "SAO": ("GRU", "CGH", "VCP"),
    "RIO": ("GIG", "SDU"),
    "YTO": ("YYZ", "YTZ"),
    "BUE": ("EZE", "AEP"),
}
AIRPORT_TO_METRO = {airport: city for city, airports in METROS.items() for airport in airports}

RETURN_NOT_FETCHED = "return not fetched"


class OddPayload(Exception):
    """The flight page was empty or not the shape the parser expects."""


def metro_of(code: str):
    """City code for an airport, or None if the code is already a city or unknown."""
    code = (code or "").upper()
    if code in METROS:
        return None
    return AIRPORT_TO_METRO.get(code)


def fallback_metro(code: str, already):
    """Metro to retry, unless that city or another of its airports is already in the request."""
    metro = metro_of(code)
    if not metro:
        return None
    requested = {item.upper() for item in already}
    if metro in requested:
        return None
    if (set(METROS[metro]) & requested) - {code.upper()}:
        return None
    return metro


def _parse_stamp(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M")


def connection_gap(arrival, departure):
    """Layover minutes at the connection airport. Local arrival vs local next departure.

    Both clocks are local to that airport, so the difference is the wait on the ground.
    A missing or negative gap is unknown, not zero.
    """
    try:
        gap = int((_parse_stamp(departure) - _parse_stamp(arrival)).total_seconds() // 60)
    except (TypeError, ValueError):
        return None
    if gap < 0:
        return None
    return gap


def door_to_door(segments: list) -> dict:
    """Flying time plus each connection wait. Unknown pieces stay unknown."""
    flying = 0
    flying_known = True
    for seg in segments:
        mins = seg.get("minutes")
        if isinstance(mins, bool) or not isinstance(mins, (int, float)) or mins < 0:
            flying_known = False
            continue
        flying += int(mins)
    layovers = []
    unknown = False
    for left, right in zip(segments, segments[1:]):
        gap = connection_gap(left.get("arr"), right.get("dep"))
        if gap is None:
            unknown = True
            continue
        layovers.append({"airport": left.get("to"), "minutes": gap})
    longest = max(layovers, key=lambda item: item["minutes"]) if layovers else None
    elapsed = None
    if flying_known and not unknown:
        elapsed = flying + sum(item["minutes"] for item in layovers)
    return {
        "flying_minutes": flying if flying_known else None,
        "elapsed_minutes": elapsed,
        "longest_layover": longest,
        "times_unknown": (not flying_known) or unknown,
    }


def leg_text(segments: list) -> str:
    if not segments:
        return "unknown"
    bits = []
    for seg in segments:
        dep = seg.get("dep") or ""
        arr = seg.get("arr") or ""
        dep_t = dep[11:16] if len(dep) >= 16 else "?"
        arr_t = arr[11:16] if len(arr) >= 16 else "?"
        bits.append("%s %s-%s %s" % (dep_t, seg.get("from") or "?", seg.get("to") or "?", arr_t))
    stops = max(len(segments) - 1, 0)
    stop_s = "nonstop" if stops == 0 else "%d stop%s" % (stops, "" if stops == 1 else "s")
    return "%s (%s, flight number unknown)" % (", ".join(bits), stop_s)


def trip_text(elapsed, return_date, ret_status) -> str:
    out = fmt_dur(elapsed) if isinstance(elapsed, int) else "unknown"
    if not return_date:
        return "out %s" % out
    if ret_status == RETURN_NOT_FETCHED:
        back = RETURN_NOT_FETCHED
    elif isinstance(ret_status, int):
        back = fmt_dur(ret_status)
    else:
        back = "unknown"
    return "out %s / back %s" % (out, back)


def _segment(single) -> dict:
    return {
        "from": single.from_airport.code,
        "to": single.to_airport.code,
        "dep": "%04d-%02d-%02d %s" % (*single.departure.date, hhmm(single.departure.time)),
        "arr": "%04d-%02d-%02d %s" % (*single.arrival.date, hhmm(single.arrival.time)),
        "minutes": single.duration,
        "aircraft": single.plane_type,
        "flight_number": None,
    }


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
    except (IndexError, TypeError, KeyError, ValueError, AttributeError) as exc:
        raise OddPayload("odd flight payload: %s" % inputs.public_error(exc)) from exc
    try:
        import history
        insight = history.extract_price_insight(html)
    except Exception as e:
        insight = {"history_points": 0, "history_note": "Could not read a price graph: %s" % inputs.public_error(e)}
    broken = 0
    for f in results or []:
        try:
            segs = [_segment(s) for s in (f.flights or [])]
            if not segs:
                continue
            first, last = segs[0], segs[-1]
            timing = door_to_door(segs)
            ret_obj = None
            ret_status = None
            if ret:
                # fast-flights' parser returns the outbound itinerary for a round-trip
                # price. It does not expose Google's second-step return selection, so
                # the return is labeled rather than guessed.
                ret_obj = {
                    "status": RETURN_NOT_FETCHED,
                    "airline": None,
                    "flight_number": None,
                    "depart": None,
                    "arrive": None,
                    "stops": None,
                    "longest_layover": None,
                    "elapsed_minutes": None,
                }
                ret_status = RETURN_NOT_FETCHED
            rows.append(
                {
                    "origin": origin,
                    "destination": dest,
                    "depart_date": dep.isoformat(),
                    "return_date": ret.isoformat() if ret else None,
                    "price": f.price,
                    "currency": currency,
                    "airlines": list(f.airlines or []),
                    "stops": len(segs) - 1,
                    "route": "-".join([segs[0]["from"]] + [s["to"] for s in segs]),
                    "depart_time": first["dep"][11:16],
                    "arrive_time": last["arr"][11:16],
                    "arrive_date": last["arr"][:10],
                    "flying_minutes": timing["flying_minutes"],
                    "elapsed_minutes": timing["elapsed_minutes"],
                    "longest_layover": timing["longest_layover"],
                    "times_unknown": timing["times_unknown"],
                    "out": leg_text(segs),
                    "back": RETURN_NOT_FETCHED if ret else None,
                    "return": ret_obj,
                    "trip": trip_text(timing["elapsed_minutes"], ret, ret_status),
                    "fare_brand": None,
                    "bags": "unknown",
                    "segments": segs,
                    "google_flights_url": q.url(),
                    "source": "Google Flights via fast-flights",
                    "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                }
            )
        except (IndexError, TypeError, KeyError, ValueError, AttributeError):
            broken += 1
            continue
    if results and not rows and broken:
        raise OddPayload("every flight result had an odd shape")
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
    elapsed = row.get("elapsed_minutes")
    if not isinstance(elapsed, int):
        elapsed = row.get("flying_minutes") if isinstance(row.get("flying_minutes"), int) else 10**9
    return (price, stops, elapsed)


def fallback_target(origin, dest, origins, dests):
    """Retry one side only. Prefer the destination airport (HND -> TYO)."""
    alt_d = fallback_metro(dest, dests)
    if alt_d:
        return origin, alt_d, dest, alt_d
    alt_o = fallback_metro(origin, origins)
    if alt_o:
        return alt_o, dest, origin, alt_o
    return None


def _needs_fallback(rows, err) -> bool:
    if isinstance(err, OddPayload):
        return True
    return err is None and not rows


def _attempt(origin, dest, dep, ret, args):
    try:
        rows, url, insight = run_query(
            origin, dest, dep, ret, args.cabin, args.adults, args.children, args.currency, args.max_stops
        )
        return rows, url, insight, None
    except Exception as exc:
        return [], None, None, exc


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
    p.add_argument("--airports", help="Alias of --origin-airports")
    p.add_argument("--origin-airports", help="Comma-separated origin airports to search and merge, e.g. LHR,LGW")
    p.add_argument("--dest-airports", help="Comma-separated destination airports to search and merge, e.g. NRT,HND")
    p.add_argument("--top", type=int, default=20, help="Rows to print in the table")
    p.add_argument("--delay", type=float, default=1.5, help="Seconds between requests (be polite; avoids blocks)")
    p.add_argument("--json-only", action="store_true", help="Print only JSON (for agents/scripts)")
    p.add_argument("--urls", action="store_true", help="Print the Google Flights URL of each query")
    p.add_argument("--history", help="JSONL file for price history (default ~/.flight-points-optimiser/history.jsonl)")
    p.add_argument("--no-history", action="store_true", help="Do not append this run to the local price history")
    a = p.parse_args(argv)

    if a.airports and a.origin_airports:
        p.error("use --origin-airports or --airports, not both")
    origins = inputs.airports(a.origin_airports or a.airports or a.origin, p)
    dests = inputs.airports(a.dest_airports or a.dest, p)
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

    all_rows, errors, urls, insights, fallbacks = [], [], [], [], []
    for o in origins:
        for dest in dests:
            for dep in daterange(dep0, a.flex):
                if dep < date.today():
                    continue
                ret = ret0 + (dep - dep0) if ret0 else None
                rows, url, insight, err = _attempt(o, dest, dep, ret, a)
                used_o, used_d = o, dest
                if _needs_fallback(rows, err):
                    target = fallback_target(o, dest, origins, dests)
                    if target:
                        fb_o, fb_d, which, metro = target
                        print(
                            "HINT %s on %s returned no usable Google Flights results. Retrying metro code %s (%s)."
                            % (which, dep.isoformat(), metro, ", ".join(METROS[metro])),
                            file=sys.stderr,
                        )
                        fallbacks.append({
                            "from": which,
                            "to": metro,
                            "date": dep.isoformat(),
                            "reason": "empty or odd payload",
                        })
                        time.sleep(a.delay)
                        rows, url, insight, err = _attempt(fb_o, fb_d, dep, ret, a)
                        used_o, used_d = fb_o, fb_d
                        for row in rows:
                            row["fallback_from"] = which
                if err:
                    errors.append({
                        "origin": used_o,
                        "destination": used_d,
                        "date": dep.isoformat(),
                        "error": inputs.public_error(err),
                    })
                else:
                    all_rows.extend(rows)
                    if url:
                        urls.append(url)
                    insights.append({
                        "origin": used_o,
                        "destination": used_d,
                        "depart_date": dep.isoformat(),
                        "return_date": ret.isoformat() if ret else None,
                        "insight": insight,
                    })
                    if rows and not a.no_history:
                        _save_history(used_o, used_d, dep, ret, a, rows, insight)
                time.sleep(a.delay)

    all_rows.sort(key=_sort_key)
    # Cheapest per date/origin/destination: a quick calendar view
    cal = {}
    for r in all_rows:
        k = (r["origin"], r["destination"], r["depart_date"])
        if k not in cal or _sort_key(r) < _sort_key(cal[k]):
            cal[k] = r
    out = {
        "query": {
            "origins": origins, "destinations": dests, "date": a.date, "return": a.ret,
            "cabin": a.cabin, "adults": a.adults, "children": a.children,
            "currency": a.currency, "flex_days": a.flex,
        },
        "fallbacks": fallbacks,
        "cheapest_by_origin_and_date": [
            {
                "origin": k[0], "destination": k[1], "depart_date": k[2],
                "price": v["price"], "airlines": v["airlines"], "stops": v["stops"],
                "elapsed_minutes": v.get("elapsed_minutes"),
            }
            for k, v in sorted(cal.items(), key=lambda kv: _sort_key(kv[1]))
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
            for r in all_rows[: a.top]:
                lay = r.get("longest_layover") or {}
                if lay.get("minutes") is None:
                    lay_s = "unknown" if r.get("times_unknown") else "none"
                else:
                    lay_s = "%s at %s" % (fmt_dur(lay["minutes"]), lay.get("airport") or "?")
                flying = fmt_dur(r["flying_minutes"]) if isinstance(r.get("flying_minutes"), int) else "unknown"
                print("%s-%s %s  %s %s  %s  %s stop(s)  %s" % (
                    r["origin"], r["destination"], r["depart_date"], a.currency or "?",
                    _fmt_price(r["price"]), ", ".join(r["airlines"])[:40], r["stops"], r["route"]))
                print("  OUT  %s" % r.get("out"))
                if r.get("return_date"):
                    print("  BACK %s" % r.get("back"))
                print("  TRIP %s; flying %s; longest layover %s" % (r.get("trip"), flying, lay_s))
                print("  fare brand unknown; bags unknown")
            if len(cal) > 1:
                print("\nCheapest per origin/date:")
                for c in out["cheapest_by_origin_and_date"]:
                    print("  %s-%s %s  %s %s" % (
                        c["origin"], c["destination"], c["depart_date"], a.currency or "?", _fmt_price(c["price"])))
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
            print("ERROR %s-%s %s: %s" % (
                e.get("origin"), e.get("destination") or "?", e["date"], inputs.one_line(e["error"])), file=sys.stderr)
        print("\n--- JSON ---")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if all_rows else 2


if __name__ == "__main__":
    sys.exit(main())
