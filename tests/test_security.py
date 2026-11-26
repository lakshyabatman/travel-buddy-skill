#!/usr/bin/env python3
"""Security checks that do not touch the network."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

import awards
import history
import inputs
import search
import watch


def _obs(**extra):
    rec = {
        "origin": "LIS",
        "destination": "GRU",
        "depart_date": "2026-12-10",
        "return_date": None,
        "cabin": "economy",
        "adults": 1,
        "children": 0,
        "currency": "EUR",
        "price": 400,
        "fetched_at": "2026-11-01T00:00:00+00:00",
        "source": "test",
        "google_history": [],
    }
    rec.update(extra)
    return rec


class HistoryStoreTests(unittest.TestCase):
    def test_file_mode_is_private_and_secrets_are_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fresh" / "history.jsonl"
            history.record_observation(
                _obs(passport="X1234567", password="secret", card="4111111111111111"),
                path,
            )
            text = path.read_text()
            self.assertNotIn("passport", text)
            self.assertNotIn("secret", text)
            self.assertNotIn("4111", text)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_existing_world_readable_file_is_chmodded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            path.write_text("")
            os.chmod(path, 0o644)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
            history.record_observation(_obs(), path)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_existing_parent_is_not_chmodded(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "keep"
            parent.mkdir()
            os.chmod(parent, 0o755)
            path = parent / "history.jsonl"
            history.record_observation(_obs(), path)
            self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_refuses_symlink_and_credentials_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "history.jsonl"
            real.write_text("")
            link = Path(tmp) / "link.jsonl"
            link.symlink_to(real)
            with self.assertRaises(ValueError):
                history.record_observation(_obs(), link)
        with self.assertRaises(ValueError):
            history.record_observation(_obs(), Path.home() / ".ssh" / "history.jsonl")

    def test_rejects_path_escape(self):
        with self.assertRaises(ValueError):
            inputs.normalize_data_path("/tmp/../etc/history.jsonl", (".jsonl",))


class SearchCliTests(unittest.TestCase):
    def test_rejects_bad_iata_date_and_currency(self):
        for argv in (
            ["MEXICO", "MAD", "2026-12-16", "--no-history"],
            ["MEX", "MAD", "2026-13-40", "--no-history"],
            ["MEX", "MAD", "2026-12-16", "--currency", "US$", "--no-history"],
            ["MEX", "MAD", "2026-12-16", "--return", "2026-12-01", "--no-history"],
            ["MEX", "MAD", "2026-12-16", "--flex", "9", "--no-history"],
            ["MEX", "MAD", "2026-12-16", "--history", "/etc/history.jsonl", "--no-history"],
        ):
            with self.assertRaises(SystemExit) as caught:
                search.main(argv)
            self.assertEqual(caught.exception.code, 2)

    def test_fetch_sets_timeout_without_calling_google(self):
        try:
            import fast_flights.fetcher  # noqa: F401
            import primp
        except ImportError:
            self.skipTest("fast-flights is not installed")
        captured = {}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                captured.update(kwargs)

            def get(self, *args, **kwargs):
                class Response:
                    text = "<html>ok</html>"

                return Response()

        original = primp.Client
        primp.Client = FakeClient
        try:
            html = search._fetch_html("test")
        finally:
            primp.Client = original
        self.assertEqual(html, "<html>ok</html>")
        self.assertEqual(captured.get("timeout"), search.FETCH_TIMEOUT_S)
        self.assertEqual(captured.get("read_timeout"), search.FETCH_TIMEOUT_S)


class WatchPathTests(unittest.TestCase):
    def test_origin_cannot_escape_the_state_directory(self):
        with self.assertRaises(ValueError):
            watch.state_path("../../etc", "MAD", "2026-12-01", None)

    def test_state_name_must_start_with_watch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                watch.state_path("LIS", "GRU", "2026-12-01", str(Path(tmp) / "package.json"))


class AwardTemplateTests(unittest.TestCase):
    def test_template_cannot_read_attributes(self):
        item = {
            "supports_prefill": True,
            "template": "https://example.test/{origin.__class__}",
        }
        with self.assertRaises(ValueError):
            awards.build(item, "LIS", "GRU", "2026-12-01", 1)

    def test_bad_airport_is_rejected(self):
        item = {"supports_prefill": True, "template": "https://example.test/{origin}"}
        with self.assertRaises(ValueError):
            awards.build(item, "../x", "GRU", "2026-12-01", 1)

    def test_safe_template_still_fills(self):
        url = awards.fill_template(
            "https://example.test/?f={origin}&t={destination}&d={depart}&n={adults}",
            {"origin": "LIS", "destination": "GRU", "depart": "2026-12-10", "adults": 2},
        )
        self.assertIn("f=LIS", url)
        self.assertIn("n=2", url)
        json.dumps({"url": url})


if __name__ == "__main__":
    unittest.main()
