#!/usr/bin/env python3
import unittest

import awards


class AwardLinkTests(unittest.TestCase):
    def setUp(self):
        self.doc = awards.load()

    def test_aeroplan_prefills_and_does_not_claim_space(self):
        item = awards.find(self.doc, "aeroplan")
        self.assertTrue(item["supports_prefill"])
        self.assertTrue(item["verified"])
        url = awards.build(item, "lis", "gru", "2026-12-10", 2)
        self.assertIn("org0=LIS", url)
        self.assertIn("dest0=GRU", url)
        self.assertIn("departureDate0=2026-12-10", url)
        self.assertIn("ADT=2", url)
        self.assertNotIn("available", url.lower())

    def test_krisflyer_has_no_template(self):
        item = awards.find(self.doc, "krisflyer")
        self.assertFalse(item["supports_prefill"])
        self.assertIsNone(awards.build(item, "SIN", "SYD", "2026-12-01", 1))

    def test_united_is_unverified(self):
        item = awards.find(self.doc, "united")
        self.assertFalse(item["verified"])
        self.assertTrue(item["supports_prefill"])

    def test_every_programme_has_a_source_and_a_date(self):
        for item in self.doc["programmes"]:
            self.assertTrue(item.get("source_url"))
            self.assertRegex(item["last_checked"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertIn("supports_prefill", item)


if __name__ == "__main__":
    unittest.main()
