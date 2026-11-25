#!/usr/bin/env python3
import unittest

import search


class TimingTests(unittest.TestCase):
    def test_elapsed_includes_the_layover(self):
        # 6h + 8h30 layover + 5h30 = 20h, not 11h30 of flying only.
        segments = [
            {"from": "LHR", "to": "DOH", "dep": "2026-05-04 09:00", "arr": "2026-05-04 15:00", "minutes": 360},
            {"from": "DOH", "to": "NRT", "dep": "2026-05-04 23:30", "arr": "2026-05-05 05:00", "minutes": 330},
        ]
        timing = search.door_to_door(segments)
        self.assertEqual(timing["flying_minutes"], 690)
        self.assertEqual(timing["elapsed_minutes"], 690 + 510)
        self.assertEqual(timing["longest_layover"], {"airport": "DOH", "minutes": 510})
        self.assertFalse(timing["times_unknown"])

    def test_negative_gap_is_unknown_not_zero(self):
        segments = [
            {"from": "LHR", "to": "DOH", "dep": "2026-05-04 09:00", "arr": "2026-05-04 18:00", "minutes": 400},
            {"from": "DOH", "to": "NRT", "dep": "2026-05-04 17:00", "arr": "2026-05-05 05:00", "minutes": 300},
        ]
        timing = search.door_to_door(segments)
        self.assertIsNone(timing["elapsed_minutes"])
        self.assertTrue(timing["times_unknown"])
        self.assertIsNone(timing["longest_layover"])


class MetroFallbackTests(unittest.TestCase):
    def test_airport_falls_back_to_its_city(self):
        self.assertEqual(search.fallback_metro("HND", ["HND"]), "TYO")
        self.assertEqual(search.fallback_metro("LHR", ["LHR"]), "LON")
        self.assertEqual(search.fallback_metro("JFK", ["JFK"]), "NYC")
        self.assertEqual(search.fallback_metro("CDG", ["CDG"]), "PAR")

    def test_retry_changes_only_the_destination_when_both_are_airports(self):
        self.assertEqual(
            search.fallback_target("LHR", "NRT", ["LHR"], ["NRT"]),
            ("LHR", "TYO", "NRT", "TYO"),
        )
        self.assertEqual(
            search.fallback_target("LHR", "LIS", ["LHR"], ["LIS"]),
            ("LON", "LIS", "LHR", "LON"),
        )
        self.assertIsNone(search.fallback_target("TYO", "SYD", ["TYO"], ["SYD"]))

    def test_city_code_and_sibling_airports_are_not_retried(self):
        self.assertIsNone(search.fallback_metro("TYO", ["TYO"]))
        self.assertIsNone(search.fallback_metro("HND", ["NRT", "HND"]))
        self.assertIsNone(search.fallback_metro("LIS", ["LIS"]))

    def test_empty_and_odd_payloads_ask_for_a_fallback(self):
        self.assertTrue(search._needs_fallback([], None))
        self.assertTrue(search._needs_fallback([], search.OddPayload("odd")))
        self.assertFalse(search._needs_fallback([{"price": 1}], None))
        self.assertFalse(search._needs_fallback([], RuntimeError("blocked")))


class RoundTripLabelTests(unittest.TestCase):
    def test_return_not_fetched_is_the_label(self):
        text = search.trip_text(1200, "2026-05-18", search.RETURN_NOT_FETCHED)
        self.assertIn("out 20h00", text)
        self.assertIn("return not fetched", text)

    def test_leg_does_not_invent_a_flight_number(self):
        text = search.leg_text([
            {"from": "LHR", "to": "NRT", "dep": "2026-05-04 09:05", "arr": "2026-05-05 05:10"},
        ])
        self.assertIn("LHR-NRT", text)
        self.assertIn("flight number unknown", text)
        self.assertNotIn("BA", text)

    def test_leg_includes_a_real_flight_number(self):
        text = search.leg_text([
            {
                "from": "JFK", "to": "LHR", "dep": "2026-12-23 18:00", "arr": "2026-12-24 06:00",
                "carrier": "B6", "flight_number": "1107",
            },
        ])
        self.assertIn("B61107", text)
        self.assertIn("JFK-LHR", text)
        self.assertNotIn("unknown", text)


class ReturnSelectionTests(unittest.TestCase):
    def test_token_carries_the_selected_outbound(self):
        import base64
        token = search.search_token(
            [(
                "2026-12-16", "LHR", "JFK",
                [{"from": "LHR", "to": "JFK", "dep": "2026-12-16 09:00", "carrier": "B6", "flight_number": "20"}],
            ), ("2026-12-23", "JFK", "LHR", [])],
            "economy", 1, 0,
        )
        raw = base64.urlsafe_b64decode(token + "==")
        self.assertIn(b"B6", raw)
        self.assertIn(b"20", raw)
        self.assertIn(b"LHR", raw)
        self.assertIn(b"JFK", raw)
        self.assertIn(b"2026-12-23", raw)

    def test_choose_return_is_cheapest_then_shortest(self):
        offers = [
            {"price": 500, "segments": [
                {"dep": "2026-12-23 08:00", "arr": "2026-12-23 12:00", "minutes": 240, "to": "LHR"},
                {"dep": "2026-12-23 18:00", "arr": "2026-12-23 20:00", "minutes": 120, "to": "CDG"},
            ]},
            {"price": 400, "segments": [
                {"dep": "2026-12-23 09:00", "arr": "2026-12-23 20:00", "minutes": 660, "to": "LHR"},
            ]},
            {"price": 400, "segments": [
                {"dep": "2026-12-23 10:00", "arr": "2026-12-23 18:00", "minutes": 480, "to": "LHR"},
            ]},
        ]
        chosen = search.choose_return(offers)
        self.assertEqual(chosen["segments"][0]["minutes"], 480)

    def test_payload_keeps_best_and_other_flights_and_the_flight_number(self):
        segment = [None] * 23
        segment[3] = "LHR"
        segment[6] = "JFK"
        segment[8] = [9, 5]
        segment[10] = [12, 30]
        segment[11] = 480
        segment[20] = [2026, 12, 16]
        segment[21] = [2026, 12, 16]
        segment[22] = ["B6", "20", None, "JetBlue"]
        offer = [["multi", ["JetBlue"], [segment]], [[None, 900]]]
        payload = [None, None, [[offer]], [[offer]]]
        found = search.offers_from_payload(payload)
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0]["segments"][0]["carrier"], "B6")
        self.assertEqual(found[0]["segments"][0]["flight_number"], "20")
        self.assertEqual(found[0]["price"], 900)

    def test_error_page_is_not_an_empty_result(self):
        html = "<script class='ds:1'>AF_initDataCallback({key: 'ds:1', data:[],errorHasStatus: true,});</script>"
        with self.assertRaises(search.GoogleErrorPage):
            search.parse_offers(html)


if __name__ == "__main__":
    unittest.main()
