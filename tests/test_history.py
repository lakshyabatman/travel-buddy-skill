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
        self.assertIn("Do not invent", insight["history_note"])

    def test_percentile_of_latest(self):
        prices = [100, 110, 120, 130, 140, 150, 160, 170, 180, 190]
        pct = history.percentile_rank(190, prices)
        self.assertGreater(pct, 90)
        self.assertEqual(history.band_from_percentile(pct), "high")
        self.assertEqual(history.band_from_percentile(10), "low")
        self.assertEqual(history.band_from_percentile(50), "typical")


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
            history.record_observation({**base, "fetched_at": "2026-11-01T00:00:00+00:00", "price": 400, "source": "test", "google_history": []}, path)
            graph = [{"date": "2026-11-0%d" % i, "price": 100 + i * 10, "at_ms": 0} for i in range(1, 10)]
            graph.append({"date": "2026-11-10", "price": 190, "at_ms": 0})
            history.record_observation({
                **base,
                "fetched_at": "2026-11-25T00:00:00+00:00",
                "price": 250,
                "source": "test",
                "google_price_level": "typical",
                "google_insight_price": 190,
                "google_range_low": 80,
                "google_range_high": 200,
                "google_history": graph,
            }, path)
            summary = history.summarize(base, path)
            self.assertEqual(summary["local_log"]["observations"], 2)
            self.assertEqual(summary["local_log"]["min"], 250)
            self.assertEqual(summary["local_log"]["max"], 400)
            self.assertEqual(summary["google_graph"]["points"], 10)
            self.assertEqual(summary["google_graph"]["latest"], 190)
            self.assertEqual(summary["google_price_level"], "typical")
            text = history.format_summary(summary)
            self.assertIn("Not a forecast", text)
            self.assertIn("typical", text)

    def test_empty_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = history.summarize({
                "origin": "NBO", "destination": "CDG", "depart_date": "2026-12-01",
                "return_date": None, "cabin": "economy", "adults": 1, "children": 0, "currency": "EUR",
            }, Path(tmp) / "missing.jsonl")
            self.assertEqual(summary["local_log"]["observations"], 0)
            self.assertEqual(summary["google_graph"]["points"], 0)


if __name__ == "__main__":
    unittest.main()
