"""Deterministic synthetic tests for the H-B exit contract."""
import unittest

from h_b_exit import H_B_TIME_STOP_BARS, evaluate_h_b_exit
from h_b_signal import H1_INTERVAL_MS


class TestHBExit(unittest.TestCase):
    def setUp(self):
        self.position = {
            "strategy": "H-B-mean-reversion",
            "direction": "long",
            "policy_version": "v0.1",
            "entry_ts_ms": 1_800_000_000_000,
            "entry_price": 100.0,
            "stop_price": 95.0,
            "target_price": 105.0,
        }

    def candle(self, held, open_=100.0, high=102.0, low=98.0, close=100.0):
        return {
            "ts": self.position["entry_ts_ms"] + (held - 1) * H1_INTERVAL_MS,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
        }

    def test_no_exit_when_no_boundary_is_touched(self):
        self.assertIsNone(evaluate_h_b_exit(self.position, self.candle(2), 2))

    def test_stop_touch_exits_at_stop(self):
        result = evaluate_h_b_exit(
            self.position, self.candle(2, high=101, low=94, close=97), 2
        )
        self.assertEqual(result["exit_reason"], "h_b_stop")
        self.assertEqual(result["exit_price"], 95.0)

    def test_stop_gap_exits_at_worse_open(self):
        result = evaluate_h_b_exit(
            self.position, self.candle(2, open_=92, high=96, low=90, close=94), 2
        )
        self.assertEqual(result["exit_price"], 92.0)

    def test_mean_target_exits_at_frozen_target(self):
        result = evaluate_h_b_exit(
            self.position, self.candle(2, high=106, low=99, close=104), 2
        )
        self.assertEqual(result["exit_reason"], "h_b_mean_target")
        self.assertEqual(result["exit_price"], 105.0)

    def test_target_gap_gets_no_price_improvement(self):
        result = evaluate_h_b_exit(
            self.position, self.candle(2, open_=108, high=110, low=107, close=109), 2
        )
        self.assertEqual(result["exit_price"], 105.0)

    def test_stop_wins_when_stop_and_target_are_both_touched(self):
        result = evaluate_h_b_exit(
            self.position, self.candle(2, high=106, low=94, close=100), 2
        )
        self.assertEqual(result["exit_reason"], "h_b_stop")
        self.assertEqual(result["exit_price"], 95.0)

    def test_fill_bar_target_is_disabled(self):
        result = evaluate_h_b_exit(
            self.position, self.candle(1, high=107, low=99, close=106), 1
        )
        self.assertIsNone(result)

    def test_fill_bar_protective_stop_remains_active(self):
        result = evaluate_h_b_exit(
            self.position, self.candle(1, high=101, low=94, close=97), 1
        )
        self.assertEqual(result["exit_reason"], "h_b_stop")

    def test_time_stop_does_not_fire_before_bar_24(self):
        self.assertIsNone(evaluate_h_b_exit(
            self.position, self.candle(H_B_TIME_STOP_BARS - 1, close=101), H_B_TIME_STOP_BARS - 1
        ))

    def test_time_stop_fires_on_close_of_bar_24(self):
        result = evaluate_h_b_exit(
            self.position, self.candle(H_B_TIME_STOP_BARS, close=101.5), H_B_TIME_STOP_BARS
        )
        self.assertEqual(result["exit_reason"], "h_b_time_stop")
        self.assertEqual(result["exit_price"], 101.5)

    def test_timestamp_must_match_holding_counter(self):
        candle = self.candle(3)
        with self.assertRaisesRegex(ValueError, "timestamp"):
            evaluate_h_b_exit(self.position, candle, 2)

    def test_invalid_position_geometry_is_rejected(self):
        position = dict(self.position, target_price=99)
        with self.assertRaisesRegex(ValueError, "stop < entry < target"):
            evaluate_h_b_exit(position, self.candle(2), 2)

    def test_invalid_ohlc_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid OHLC"):
            evaluate_h_b_exit(self.position, self.candle(2, high=90), 2)

    def test_unsupported_policy_is_rejected(self):
        position = dict(self.position, policy_version="v2")
        with self.assertRaisesRegex(ValueError, "policy version"):
            evaluate_h_b_exit(position, self.candle(2), 2)

    def test_holding_counter_outside_frozen_window_is_rejected(self):
        for bars_held in (0, H_B_TIME_STOP_BARS + 1, True):
            with self.assertRaisesRegex(ValueError, "bars_held"):
                evaluate_h_b_exit(self.position, self.candle(2), bars_held)


if __name__ == "__main__":
    unittest.main()
