#!/usr/bin/env python3
"""History store and Google price-graph extraction. No network."""
import json
import tempfile
import unittest
from pathlib import Path

import history


def _html(block):
    payload = [None, None, None, None, None, block]
    return (
        '<script class="ds:1">callback({data:'
        + json.dumps(payload)
        + ', sideChannel: {}});</script>'
        + '<h3>Price insights</h3><div>Prices are currently <span>typical</span></div>'
    )


def _block():
    start = 1700000000000
    series = [[start + i * 86400000, 100 + i * 10] for i in range(10)]
    block = [None] * 11
    block[0] = 3
    block[1] = [None, series[-1][1]]
    block[2] = [None, 80]
    block[5] = [None, 200]
    block[10] = [series]
    return block


class ExtractTests(unittest.TestCase):
    def test_graph_level_and_range(self):
        insight = history.extract_price_insight(_html(_block()))
        self.assertEqual(insight["quote"], "prices are currently typical")
        self.assertEqual(insight["price_level"], "typical")
        self.assertEqual(insight["history_points"], 10)
        self.assertEqual(insight["insight_price"], 190)
        self.assertEqual(insight["range_low"], 80)
        self.assertEqual(insight["range_high"], 200)
        self.assertEqual(insight["history"][0]["price"], 100)
        self.assertEqual(insight["history"][-1]["price"], 190)

    def test_missing_graph_does_not_invent(self):
        insight = history.extract_price_insight("<html><body>No flights widget</body></html>")
        self.assertEqual(insight["history"], [])
        self.assertIsNone(insight["price_level"])
        self.assertIsNone(insight["quote"])
        self.assertIn("Do not invent", insight["history_note"])

    def test_quotes_other_google_phrases(self):
        html = "<p>Prices are likely to increase and are less than usual.</p>"
        quote = history.insight_quote(html)
        self.assertIn("likely to increase", quote)
        self.assertIn("less than usual", quote)


class StoreTests(unittest.TestCase):
    def test_log_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            base = {
                "origin": "LIS",
                "destination": "GRU",
                "depart_date": "2026-12-10",
                "return_date": None,
                "cabin": "economy",
                "adults": 1,
                "children": 0,
                "currency": "EUR",
            }
            history.record_observation({**base, "fetched_at": "2026-11-01T00:00:00+00:00", "price": 400, "source": "test"}, path)
            history.record_observation({
                **base,
                "fetched_at": "2026-11-25T00:00:00+00:00",
                "price": 250,
                "source": "test",
                "google_price_level": "typical",
            }, path)
            summary = history.summarize(base, path)
            self.assertEqual(summary["local_log"]["observations"], 2)
            self.assertEqual(summary["local_log"]["first_seen"], "2026-11-01")
            self.assertFalse(summary["local_log"]["enough"])
            self.assertEqual(summary["google_quote"], "prices are currently typical")
            self.assertEqual(summary["verdict"]["verdict"], "Watch")
            text = history.format_summary(summary)
            self.assertIn("not enough history", text)
            self.assertIn("This is not a forecast", text)
            self.assertIn("2 observation", text)

    def test_empty_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = history.summarize({
                "origin": "NBO", "destination": "CDG", "depart_date": "2026-12-01",
                "return_date": None, "cabin": "economy", "adults": 1, "children": 0, "currency": "EUR",
            }, Path(tmp) / "missing.jsonl")
            self.assertEqual(summary["local_log"]["observations"], 0)
            self.assertEqual(summary["verdict"]["verdict"], "Not enough data")


class VerdictTests(unittest.TestCase):
    def _local(self, n, span, prices):
        return {"observations": n, "enough": n >= 5 and span >= 7, "new_low": False, "first_seen": "2026-11-01", "latest": prices[-1]}

    def test_google_low_is_book_now(self):
        verdict = history.cash_verdict("prices are currently low", self._local(0, 0, [0]))
        self.assertEqual(verdict["verdict"], "Book now")

    def test_likely_to_increase_is_book_now(self):
        verdict = history.cash_verdict("likely to increase", self._local(1, 0, [10]))
        self.assertEqual(verdict["verdict"], "Book now")

    def test_typical_is_watch(self):
        verdict = history.cash_verdict("prices are currently typical", self._local(1, 0, [10]))
        self.assertEqual(verdict["verdict"], "Watch")

    def test_thin_log_is_not_enough(self):
        verdict = history.cash_verdict(None, self._local(2, 3, [10, 9]))
        self.assertEqual(verdict["verdict"], "Not enough data")

    def test_new_low_with_enough_data_is_book_now(self):
        local = self._local(6, 10, [20, 18])
        local["new_low"] = True
        local["enough"] = True
        verdict = history.cash_verdict(None, local)
        self.assertEqual(verdict["verdict"], "Book now")


if __name__ == "__main__":
    unittest.main()
