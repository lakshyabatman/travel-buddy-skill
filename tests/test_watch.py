#!/usr/bin/env python3
"""Decision rules for watch.py. No network and no booking."""
import unittest

import watch


class DecideTests(unittest.TestCase):
    def test_baseline_is_quiet(self):
        alert, reason = watch.decide(None, None, 500, None)
        self.assertFalse(alert)
        self.assertIn("baseline", reason)

    def test_baseline_under_threshold_alerts_once(self):
        alert, _ = watch.decide(None, None, 400, 450)
        self.assertTrue(alert)

    def test_new_low(self):
        alert, reason = watch.decide(500, 500, 420, None)
        self.assertTrue(alert)
        self.assertEqual(reason, "new low")

    def test_same_price_does_not_repeat(self):
        alert, _ = watch.decide(400, 400, 400, 450)
        self.assertFalse(alert)

    def test_threshold_after_a_different_alert(self):
        alert, reason = watch.decide(300, 300, 400, 450)
        self.assertTrue(alert)
        self.assertIn("threshold", reason)

    def test_higher_price_is_not_a_drop(self):
        alert, _ = watch.decide(400, 400, 500, None)
        self.assertFalse(alert)


if __name__ == "__main__":
    unittest.main()
