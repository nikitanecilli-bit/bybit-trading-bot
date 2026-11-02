#!/usr/bin/env python3
"""Regression tests for the research multi-bar limit-wait policy."""
import unittest

from multibar_limit_wait import evaluate_limit_wait, prepare_signal_for_next_bar_fill


class MultiBarLimitWaitTests(unittest.TestCase):
    def test_long_order_can_fill_on_second_wait_bar(self):
        self.assertEqual(evaluate_limit_wait("long", 99.90, 101.0, 100.0, 5.0, 1, 3), ("fill", 2))

    def test_long_order_can_fill_on_third_and_last_wait_bar(self):
        self.assertEqual(evaluate_limit_wait("long", 99.90, 101.0, 100.0, 5.0, 2, 3), ("fill", 3))

    def test_order_expires_after_last_eligible_bar(self):
        self.assertEqual(evaluate_limit_wait("long", 100.0, 101.0, 100.0, 5.0, 2, 3), ("expire", 3))

    def test_order_waits_before_expiry(self):
        self.assertEqual(evaluate_limit_wait("long", 100.0, 101.0, 100.0, 5.0, 0, 3), ("wait", 1))

    def test_short_order_uses_symmetric_high_penetration(self):
        self.assertEqual(evaluate_limit_wait("short", 99.0, 100.10, 100.0, 5.0, 1, 3), ("fill", 2))

    def test_short_order_waits_when_high_does_not_penetrate(self):
        self.assertEqual(evaluate_limit_wait("short", 99.0, 100.04, 100.0, 5.0, 1, 3), ("wait", 2))

    def test_invalid_direction_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_limit_wait("sideways", 99.0, 101.0, 100.0, 5.0, 0, 3)

    def test_original_signal_timestamp_is_preserved(self):
        signal = {"signal_ts": 1_000, "direction": "long"}
        origin = prepare_signal_for_next_bar_fill(signal, 10_000, 3_600_000)
        self.assertEqual(origin, 1_000)
        self.assertEqual(signal["signal_origin_ts"], 1_000)
        self.assertEqual(signal["signal_ts"], -3_590_000)


if __name__ == "__main__":
    unittest.main()
