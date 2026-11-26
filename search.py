#!/usr/bin/env python3
"""Google Flights helper for the flight-points-optimiser skill.

Uses the free, unofficial `fast-flights` library (https://github.com/AWeirdDev/fast-flights),
which scrapes Google Flights. No API key, no paid API. Because it scrapes, it can break
whenever Google changes its page, or get rate-limited. If it fails, fall back to opening
Google Flights / Skyscanner in a browser (the URL of each query is printed with --urls).

Prices are what Google Flights showed at fetch time, in the requested currency, for ALL
passengers combined. For round trips, the listed segments are the OUTBOUND legs and the
price on a round trip is the total from a second search that names the outbound
flight. That search is done for a few outbound options only. If it fails, the return
is a same-airline one-way schedule labeled as not price-linked, never a guessed fare.
Elapsed time includes layovers. Always re-check the fare before booking.

Examples:
  python search.py MEX MAD 2026-12-16 --currency MXN
  python search.py SIN SYD 2027-01-10 --return 2027-01-17 --cabin business --currency AUD
  python search.py GRU LIS 2027-02-05 --flex 3 --currency BRL --top 15
  python search.py NBO CDG 2027-03-01 --json-only > out.json
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from datetime import date, datetime, timedelta

import inputs

FETCH_TIMEOUT_S = 20
MAX_HTML_CHARS = 4_000_000


def daterange(center: date, flex: int):
    for d in range(-flex, flex + 1):
        yield center + timedelta(days=d)


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
LIKELY_RETURN = "likely return flights (schedule only, not price-linked)"
PRICED_RETURN = "priced round-trip"
# Public Google consent value. Without it this client gets an ErrorResponse
# instead of the flight list. It is not a user credential.
SOCS = "CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAmVuIAEaBgiA_LyaBg"
SEAT_CODE = {"economy": 1, "premium-economy": 2, "business": 3, "first": 4}
_CARRIER = re.compile(r"^[A-Z0-9]{2}$")
_FLIGHT_NO = re.compile(r"^[0-9]{1,5}$")


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
        flight = ""
        carrier = seg.get("carrier")
        number = seg.get("flight_number")
        if carrier and number:
            flight = "%s%s " % (carrier, number)
        bits.append("%s%s %s-%s %s" % (flight, dep_t, seg.get("from") or "?", seg.get("to") or "?", arr_t))
    stops = max(len(segments) - 1, 0)
    stop_s = "nonstop" if stops == 0 else "%d stop%s" % (stops, "" if stops == 1 else "s")
    numbered = all(seg.get("carrier") and seg.get("flight_number") for seg in segments)
    tail = stop_s if numbered else "%s, flight number unknown" % stop_s
    return "%s (%s)" % (", ".join(bits), tail)


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


class GoogleErrorPage(Exception):
    """Google answered with an error page instead of a flight list."""


def _varint(number: int) -> bytes:
    out = bytearray()
    while True:
        piece = number & 0x7F
        number >>= 7
        if number:
            out.append(piece | 0x80)
        else:
            out.append(piece)
            return bytes(out)


def _field(number: int, wire: int) -> bytes:
    return _varint((number << 3) | wire)


def _text_field(number: int, text: str) -> bytes:
    raw = text.encode()
    return _field(number, 2) + _varint(len(raw)) + raw


def _message_field(number: int, body: bytes) -> bytes:
    return _field(number, 2) + _varint(len(body)) + body


def _varint_field(number: int, value: int) -> bytes:
    return _field(number, 0) + _varint(value)


def _selected_flight(segment: dict) -> bytes:
    return (
        _text_field(1, segment["from"])
        + _text_field(2, segment["dep"][:10])
        + _text_field(3, segment["to"])
        + _text_field(5, segment["carrier"])
        + _text_field(6, segment["flight_number"])
    )


def _flight_data(when: str, origin: str, dest: str, selected: list, max_stops=None) -> bytes:
    body = _text_field(2, when)
    for segment in selected:
        body += _message_field(4, _selected_flight(segment))
    if max_stops is not None:
        body += _varint_field(5, max_stops)
    body += _message_field(13, _text_field(2, origin))
    body += _message_field(14, _text_field(2, dest))
    return body


def search_token(legs: list, cabin: str, adults: int, children: int, max_stops=None) -> str:
    """tfs token. A selected outbound puts each segment in the first leg's field 4."""
    body = b""
    for when, origin, dest, selected in legs:
        body += _message_field(3, _flight_data(when, origin, dest, selected, max_stops))
    for _ in range(adults):
        body += _varint_field(8, 1)
    for _ in range(children):
        body += _varint_field(8, 2)
    body += _varint_field(9, SEAT_CODE[cabin])
    body += _varint_field(19, 1 if len(legs) > 1 else 2)
    return base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")


def search_url(token: str, currency: str) -> str:
    url = "https://www.google.com/travel/flights/search?tfs=%s&hl=en" % token
    if currency:
        url += "&curr=%s" % currency
    return url


def _clock(value) -> str:
    padded = [*(value or []), None, None]
    return "%02d:%02d" % (padded[0] or 0, padded[1] or 0)


def _flight_id(raw):
    if not isinstance(raw, list) or len(raw) < 2:
        return None, None, None
    carrier = raw[0] if isinstance(raw[0], str) else ""
    number = raw[1] if isinstance(raw[1], str) else (str(raw[1]) if isinstance(raw[1], int) else "")
    name = raw[3] if len(raw) > 3 and isinstance(raw[3], str) else None
    if not _CARRIER.fullmatch(carrier) or not _FLIGHT_NO.fullmatch(number):
        return None, None, name
    return carrier, number, name


def _raw_segment(raw) -> dict:
    if not isinstance(raw, list) or len(raw) < 21:
        raise ValueError("short segment")
    carrier, number, name = _flight_id(raw[22] if len(raw) > 22 else None)
    depart = "%04d-%02d-%02d %s" % (*raw[20], _clock(raw[8]))
    arrive = "%04d-%02d-%02d %s" % (*raw[21], _clock(raw[10]))
    minutes = raw[11] if isinstance(raw[11], int) and not isinstance(raw[11], bool) else None
    return {
        "from": raw[3],
        "to": raw[6],
        "dep": depart,
        "arr": arrive,
        "minutes": minutes,
        "carrier": carrier,
        "flight_number": number,
        "airline": name,
    }


def _raw_offer(item) -> dict | None:
    flight = item[0]
    price = item[1][0][1]
    if isinstance(price, bool) or not isinstance(price, int):
        return None
    segments = [_raw_segment(raw) for raw in flight[2]]
    if not segments:
        return None
    airlines = flight[1] if isinstance(flight[1], list) else []
    return {
        "price": price,
        "airlines": [name for name in airlines if isinstance(name, str)],
        "segments": segments,
    }


def offers_from_payload(payload) -> list:
    if not isinstance(payload, list):
        raise OddPayload("flight payload was not a list")
    offers = []
    for index in (2, 3):
        if index >= len(payload) or not isinstance(payload[index], list):
            continue
        node = payload[index]
        if not node or not isinstance(node[0], list):
            continue
        for item in node[0]:
            try:
                offer = _raw_offer(item)
            except (IndexError, TypeError, KeyError, ValueError):
                continue
            if offer:
                offers.append(offer)
    return offers


def parse_offers(html: str) -> list:
    from selectolax.lexbor import LexborHTMLParser

    script = LexborHTMLParser(html).css_first(r"script.ds\:1")
    text = script.text() if script is not None else ""
    if not text:
        raise OddPayload("flight page had no data script")
    head = text[:800]
    if "ErrorResponse" in head or "errorHasStatus: true" in head:
        raise GoogleErrorPage(
            "Google returned an error page instead of a flight list. "
            "That is a consent or block response, not an empty route."
        )
    try:
        data = text.split("data:", 1)[1].rsplit(",", 1)[0]
        payload = json.loads(data)
    except (IndexError, json.JSONDecodeError, ValueError) as exc:
        raise OddPayload("odd flight payload") from exc
    return offers_from_payload(payload)


def selectable(offer) -> bool:
    return all(seg.get("carrier") and seg.get("flight_number") for seg in offer["segments"])


def choose_return(offers: list):
    """Cheapest return, then shortest door-to-door, then fewest segments."""
    usable = [offer for offer in offers if offer.get("segments")]
    if not usable:
        return None

    def key(offer):
        timing = door_to_door(offer["segments"])
        elapsed = timing["elapsed_minutes"]
        return (
            offer["price"] if isinstance(offer["price"], int) else 10**12,
            elapsed if isinstance(elapsed, int) else 10**9,
            len(offer["segments"]),
        )

    return min(usable, key=key)


def _fetch_html(url: str) -> str:
    """Fetch a Google Flights URL. The consent cookie is what returns a flight list."""
    from primp import Client

    client = Client(
        impersonate="chrome_146",
        impersonate_os="windows",
        timeout=FETCH_TIMEOUT_S,
        connect_timeout=10,
        read_timeout=FETCH_TIMEOUT_S,
    )
    try:
        response = client.get(url, headers={"Cookie": "SOCS=%s" % SOCS})
        html = response.text
    except Exception as exc:
        raise RuntimeError(inputs.public_error(exc)) from exc
    if not isinstance(html, str):
        raise RuntimeError("flight response was not text")
    if len(html) > MAX_HTML_CHARS:
        raise RuntimeError("flight response exceeded %d characters" % MAX_HTML_CHARS)
    return html


def _insight(html: str):
    try:
        import history
        return history.extract_price_insight(html)
    except Exception as exc:
        return {"history_points": 0, "history_note": "Could not read a price graph: %s" % inputs.public_error(exc)}


def _load_offers(url: str):
    html = _fetch_html(url)
    try:
        offers = parse_offers(html)
    except GoogleErrorPage:
        return html, [], _insight(html), "error"
    return html, offers, _insight(html), "ok"


def _row(origin, dest, dep, ret, currency, url, outbound, back, price, status, note):
    segs = outbound["segments"]
    timing = door_to_door(segs)
    back_segs = (back or {}).get("segments") or []
    back_timing = door_to_door(back_segs) if back_segs else None
    back_elapsed = back_timing["elapsed_minutes"] if back_timing else None
    if status == PRICED_RETURN:
        back_text = leg_text(back_segs)
        ret_status = back_elapsed
    elif status == LIKELY_RETURN:
        back_text = "%s: %s" % (LIKELY_RETURN, leg_text(back_segs))
        ret_status = back_elapsed
    else:
        back_text = RETURN_NOT_FETCHED
        ret_status = RETURN_NOT_FETCHED
    first, last = segs[0], segs[-1]
    return {
        "origin": origin,
        "destination": dest,
        "depart_date": dep.isoformat(),
        "return_date": ret.isoformat() if ret else None,
        "price": price,
        "currency": currency,
        "airlines": outbound.get("airlines") or [],
        "stops": len(segs) - 1,
        "route": "-".join([segs[0]["from"]] + [seg["to"] for seg in segs]),
        "depart_time": first["dep"][11:16],
        "arrive_time": last["arr"][11:16],
        "arrive_date": last["arr"][:10],
        "flying_minutes": timing["flying_minutes"],
        "elapsed_minutes": timing["elapsed_minutes"],
        "longest_layover": timing["longest_layover"],
        "times_unknown": timing["times_unknown"],
        "out": leg_text(segs),
        "back": back_text if ret else None,
        "return": None if not ret else {
            "status": status,
            "note": note,
            "price": price if status == PRICED_RETURN else None,
            "stops": max(len(back_segs) - 1, 0) if back_segs else None,
            "elapsed_minutes": back_elapsed,
            "longest_layover": back_timing["longest_layover"] if back_timing else None,
            "segments": back_segs or None,
        },
        "trip": trip_text(timing["elapsed_minutes"], ret, ret_status if ret else None),
        "fare_brand": None,
        "bags": "unknown",
        "segments": segs,
        "google_flights_url": url,
        "source": "Google Flights",
        "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def _same_airline(outbound, offer) -> bool:
    wanted = {seg["carrier"] for seg in outbound["segments"] if seg.get("carrier")}
    found = {seg["carrier"] for seg in offer["segments"] if seg.get("carrier")}
    return bool(wanted and wanted & found)


def run_query(origin, dest, dep, ret, cabin, adults, children, currency, max_stops, return_picks=3, pause=0):
    _load_flights()
    when = dep.isoformat()
    one_way = search_url(
        search_token([(when, origin, dest, [])], cabin, adults, children, max_stops), currency,
    )
    if not ret:
        _html, offers, insight, status = _load_offers(one_way)
        if status == "error":
            raise GoogleErrorPage(
                "Google returned an error page instead of a flight list. "
                "That is a consent or block response, not an empty route."
            )
        rows = [
            _row(origin, dest, dep, None, currency, one_way, offer, None, offer["price"], None, None)
            for offer in offers
        ]
        return rows, one_way, insight

    back_when = ret.isoformat()
    round_url = search_url(
        search_token(
            [(when, origin, dest, []), (back_when, dest, origin, [])],
            cabin, adults, children, max_stops,
        ),
        currency,
    )
    html, offers, insight, status = _load_offers(round_url)
    note = None
    if status != "ok" or not offers:
        if pause:
            time.sleep(pause)
        html, offers, insight, status = _load_offers(one_way)
        note = "Outbound list is the one-way search. The round-trip page had no itineraries."
        if status == "error":
            raise GoogleErrorPage(
                "Google returned an error page instead of a flight list. "
                "That is a consent or block response, not an empty route."
            )
    ranked = sorted(
        (offer for offer in offers if selectable(offer)),
        key=lambda offer: offer["price"],
    )[:return_picks]
    if not ranked:
        return [
            _row(origin, dest, dep, ret, currency, round_url, offer, None, None, RETURN_NOT_FETCHED, note)
            for offer in offers[:return_picks]
        ], round_url, insight or _insight(html)
    rows = []
    schedule = None
    for offer in ranked:
        if pause:
            time.sleep(pause)
        token = search_token(
            [(when, origin, dest, offer["segments"]), (back_when, dest, origin, [])],
            cabin, adults, children, max_stops,
        )
        url = search_url(token, currency)
        _html, backs, _back_insight, back_status = _load_offers(url)
        chosen = choose_return(backs) if back_status == "ok" else None
        if chosen:
            rows.append(_row(
                origin, dest, dep, ret, currency, url, offer, chosen, chosen["price"], PRICED_RETURN, note,
            ))
            continue
        if schedule is None:
            if pause:
                time.sleep(pause)
            schedule_url = search_url(
                search_token([(back_when, dest, origin, [])], cabin, adults, children, max_stops),
                currency,
            )
            _html, schedule, _ignored, _schedule_status = _load_offers(schedule_url)
            schedule = schedule or []
        match = choose_return([item for item in schedule if _same_airline(offer, item)])
        if match:
            rows.append(_row(
                origin, dest, dep, ret, currency, url, offer, match, None, LIKELY_RETURN,
                "One-way schedule on the return date for the same airline. Not the round-trip price.",
            ))
        else:
            rows.append(_row(
                origin, dest, dep, ret, currency, url, offer, None, None, RETURN_NOT_FETCHED, note,
            ))
    return rows, round_url, insight or _insight(html)


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
                "google_quote": insight.get("quote"),
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
            origin, dest, dep, ret, args.cabin, args.adults, args.children, args.currency, args.max_stops,
            return_picks=args.return_picks, pause=args.delay,
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
    p.add_argument("--return-picks", type=int, default=3, help="Round-trip outbound options whose return is fetched (1-5)")
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
    a.return_picks = inputs.bounded_int(a.return_picks, "--return-picks", p, 1, 5)
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
                "quote": (item["insight"] or {}).get("quote"),
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
            notes = []
            for r in all_rows:
                note = (r.get("return") or {}).get("note")
                if note and note not in notes:
                    notes.append(note)
            for note in notes:
                print(note)
            for item in insights:
                ins = item["insight"] or {}
                if ins.get("quote"):
                    print('Google %s %s: "%s". Future prices may not behave as expected. This is not a forecast.' % (
                        item["origin"], item["depart_date"], ins.get("quote")))
                else:
                    print("No Google price insight for %s %s. Do not invent one." % (
                        item["origin"], item["depart_date"]))
        else:
            if errors:
                print("No flight list was returned. See the error below.", file=sys.stderr)
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
