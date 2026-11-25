#!/usr/bin/env python3
"""Shared checks for search.py, history.py, watch.py, and awards.py.

CLI values and filenames are validated here. Web pages are not. Nothing in
this module opens a network connection.
"""
from __future__ import annotations

import math
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path

IATA_RE = re.compile(r"^[A-Z]{3}$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CABINS = {"economy", "premium-economy", "business", "first"}
SENSITIVE_DIRS = {".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker"}
LEVELS = {"low", "typical", "high"}
SOURCE_RE = re.compile(r"^[A-Za-z0-9 .,:/_-]{1,80}$")
FETCHED_RE = re.compile(r"^[0-9T:+.\-Z]{10,40}$")


def fail(parser, message: str):
    if parser is not None:
        parser.error(message)
    raise ValueError(message)


def iata(value, label: str = "airport", parser=None) -> str:
    code = str(value or "").strip().upper()
    if not IATA_RE.fullmatch(code):
        fail(parser, "%s must be a 3-letter IATA code" % label)
    return code


def airports(value, parser=None) -> list:
    parts = [part.strip() for part in str(value or "").split(",") if part.strip()]
    if not parts or len(parts) > 6:
        fail(parser, "provide 1 to 6 IATA airport codes")
    return [iata(part, "airport", parser) for part in parts]


def iso_date(value, label: str, parser=None) -> date:
    text = str(value or "").strip()
    if not DATE_RE.fullmatch(text):
        fail(parser, "%s must be YYYY-MM-DD" % label)
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        fail(parser, "%s must be a real date in YYYY-MM-DD" % label)


def currency(value, parser=None) -> str:
    if value is None or str(value).strip() == "":
        return ""
    code = str(value).strip().upper()
    if not CURRENCY_RE.fullmatch(code):
        fail(parser, "currency must be a 3-letter ISO 4217 code")
    return code


def cabin(value, parser=None) -> str:
    text = str(value or "").strip().lower()
    if text not in CABINS:
        fail(parser, "cabin must be economy, premium-economy, business, or first")
    return text


def bounded_int(value, label: str, parser, lo: int, hi: int) -> int:
    if isinstance(value, bool):
        fail(parser, "%s must be an integer" % label)
    try:
        number = int(value)
    except (TypeError, ValueError):
        fail(parser, "%s must be an integer" % label)
    if number < lo or number > hi:
        fail(parser, "%s must be between %s and %s" % (label, lo, hi))
    return number


def delay_seconds(value, parser=None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        fail(parser, "--delay must be a number of seconds")
    if not math.isfinite(number) or number < 0 or number > 30:
        fail(parser, "--delay must be between 0 and 30 seconds")
    return number


def one_line(value, limit: int = 240) -> str:
    text = " ".join(str(value).split())
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def public_error(exc: BaseException, limit: int = 240) -> str:
    return one_line("%s: %s" % (type(exc).__name__, exc), limit)


def _lexical(path: Path) -> Path:
    raw = str(path)
    if "\x00" in raw or "\n" in raw or "\r" in raw:
        raise ValueError("invalid path")
    path = path.expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    parts = path.parts
    if not parts or parts[0] != os.sep:
        raise ValueError("path must be absolute after expansion")
    acc = Path(parts[0])
    for part in parts[1:]:
        if part in ("", "."):
            continue
        if part == "..":
            acc = acc.parent
            continue
        if part in SENSITIVE_DIRS:
            raise ValueError("refusing to use a credentials directory")
        candidate = acc / part
        if candidate.is_symlink():
            raise ValueError("refusing to follow a symlink: %s" % candidate)
        acc = candidate
    return acc


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _allowed(path: Path) -> bool:
    roots = [Path.home(), Path.cwd(), Path(tempfile.gettempdir())]
    for root in roots:
        try:
            base = _lexical(root)
        except ValueError:
            continue
        if path == base or _within(path, base):
            return True
    return False


def normalize_data_path(path, suffixes: tuple) -> Path:
    if not isinstance(path, Path):
        path = Path(str(path))
    if not str(path).strip():
        raise ValueError("path is empty")
    acc = _lexical(path)
    if suffixes and acc.suffix not in suffixes:
        raise ValueError("file must end with %s" % " or ".join(suffixes))
    if not _allowed(acc):
        raise ValueError(
            "path must stay under your home directory, the current directory, or the temp directory"
        )
    return acc


def prepare_data_file(path, suffixes: tuple) -> Path:
    """Create the parent of a data file without following a symlink."""
    acc = normalize_data_path(path, suffixes)
    parent = acc.parent
    if parent.is_symlink():
        raise ValueError("refusing to follow a symlink: %s" % parent)
    created = not parent.exists()
    old = os.umask(0o077)
    try:
        parent.mkdir(parents=True, exist_ok=True)
    finally:
        os.umask(old)
    private_dir = parent.name == ".flight-points-optimiser" or (
        created and parent != Path.home() and parent.name not in {"tmp", "temp"}
    )
    if private_dir:
        os.chmod(parent, 0o700)
    return acc


def _open_private(path: Path, flags: int):
    try:
        fd = os.open(path, flags | os.O_NOFOLLOW, 0o600)
    except OSError as exc:
        raise ValueError("refusing to open %s (%s)" % (path, exc.errno)) from exc
    os.fchmod(fd, 0o600)
    return fd


def append_private(path: Path, text: str) -> None:
    if text.count("\n") != 1 or not text.endswith("\n"):
        raise ValueError("appended records must be a single line")
    fd = _open_private(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)


def write_private_text(path: Path, text: str) -> None:
    fd = _open_private(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)):
        return None
    return int(value)


def _history_point(item):
    if not isinstance(item, dict):
        return None
    raw_date = item.get("date")
    if not isinstance(raw_date, str):
        return None
    try:
        iso_date(raw_date, "history date")
    except ValueError:
        return None
    price = _number(item.get("price"))
    if price is None:
        return None
    point = {"date": raw_date, "price": price}
    at_ms = item.get("at_ms")
    if isinstance(at_ms, int) and not isinstance(at_ms, bool) and 0 <= at_ms <= 10**15:
        point["at_ms"] = at_ms
    return point


def sanitize_observation(rec: dict) -> dict:
    """Keep route and price fields. Drop names, documents, and secrets."""
    if not isinstance(rec, dict):
        raise ValueError("observation must be an object")
    origin = iata(rec.get("origin"), "origin")
    destination = iata(rec.get("destination"), "destination")
    depart = iso_date(rec.get("depart_date"), "departure date").isoformat()
    ret = rec.get("return_date")
    if ret not in (None, ""):
        ret = iso_date(ret, "return date").isoformat()
    else:
        ret = None
    price = _number(rec.get("price"))
    if price is None:
        raise ValueError("price must be a number")
    clean = {
        "origin": origin,
        "destination": destination,
        "depart_date": depart,
        "return_date": ret,
        "cabin": cabin(rec.get("cabin") or "economy"),
        "adults": bounded_int(rec.get("adults", 1), "adults", None, 1, 9),
        "children": bounded_int(rec.get("children", 0), "children", None, 0, 9),
        "currency": currency(rec.get("currency") or ""),
        "price": price,
    }
    fetched = rec.get("fetched_at")
    if isinstance(fetched, str) and FETCHED_RE.fullmatch(fetched):
        clean["fetched_at"] = fetched
    source = rec.get("source")
    if isinstance(source, str) and SOURCE_RE.fullmatch(source):
        clean["source"] = source
    level = rec.get("google_price_level")
    if isinstance(level, str) and level.lower() in LEVELS:
        clean["google_price_level"] = level.lower()
    for key in ("google_insight_price", "google_range_low", "google_range_high"):
        number = _number(rec.get(key))
        if number is not None:
            clean[key] = number
    graph = rec.get("google_history") or []
    if graph and not isinstance(graph, list):
        raise ValueError("google_history must be a list")
    points = []
    for item in graph[:400]:
        point = _history_point(item)
        if point:
            points.append(point)
    clean["google_history"] = points
    return clean
