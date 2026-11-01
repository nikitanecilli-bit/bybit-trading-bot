"""Tests for cumulative funding cashflows used by both MTM and final PnL."""
import unittest
from types import SimpleNamespace
from decimal import Decimal

from funding_accounting import accrued_funding_cost


ENTRY = 1_000
SETTLE_1 = 2_000
SETTLE_2 = 3_000
EVENTS = [{"ts": SETTLE_1, "rate": "0.01"},
          {"ts": SETTLE_2, "rate": "0.01"}]
MARKS = {SETTLE_1: "100", SETTLE_2: "120"}


def position(direction="long", tp1=False, tp1_ts=None, remaining="0.5"):
    return SimpleNamespace(
        entry_ts=ENTRY, entry_price="100", size_usdt="1000",
        direction=direction, remaining_fraction=remaining,
        tp1_hit=tp1, tp1_ts_ms=tp1_ts,
    )


class AccruedFundingTests(unittest.TestCase):
    def test_long_pays_positive_funding_and_short_receives(self):
        self.assertEqual(accrued_funding_cost(position(), EVENTS, MARKS, SETTLE_2),
                         Decimal("22.00"))
        self.assertEqual(accrued_funding_cost(position("short"), EVENTS, MARKS, SETTLE_2),
                         Decimal("-22.00"))

    def test_as_of_is_cumulative_and_excludes_future_settlements(self):
        self.assertEqual(accrued_funding_cost(position(), EVENTS, MARKS, SETTLE_1),
                         Decimal("10.00"))
        self.assertEqual(accrued_funding_cost(position(), EVENTS, MARKS, SETTLE_1 - 1),
                         Decimal("0.00"))

    def test_entry_timestamp_is_excluded_and_as_of_timestamp_included(self):
        events = [{"ts": ENTRY, "rate": "0.1"}, {"ts": SETTLE_1, "rate": "0.01"}]
        self.assertEqual(accrued_funding_cost(position(), events, MARKS, SETTLE_1),
                         Decimal("10.00"))

    def test_partial_tp1_applies_only_after_tp1_close_boundary(self):
        pos = position(tp1=True, tp1_ts=SETTLE_1, remaining="0.5")
        self.assertEqual(accrued_funding_cost(pos, EVENTS, MARKS, SETTLE_2),
                         Decimal("16.00"))
        before_tp1 = position(tp1=True, tp1_ts=SETTLE_2 + 1, remaining="0.5")
        self.assertEqual(accrued_funding_cost(before_tp1, EVENTS, MARKS, SETTLE_2),
                         Decimal("22.00"))

    def test_missing_exact_mark_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "Missing exact"):
            accrued_funding_cost(position(), EVENTS, {SETTLE_1: 100}, SETTLE_2)

    def test_duplicate_settlement_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            accrued_funding_cost(position(), EVENTS + [dict(EVENTS[0])], MARKS, SETTLE_2)

    def test_invalid_position_state_rejected(self):
        with self.assertRaisesRegex(ValueError, "tp1_ts_ms"):
            accrued_funding_cost(position(tp1=True), EVENTS, MARKS, SETTLE_2)
        with self.assertRaisesRegex(ValueError, "direction"):
            accrued_funding_cost(position("sideways"), EVENTS, MARKS, SETTLE_2)

    def test_zero_remaining_fraction_means_no_post_tp1_funding(self):
        pos = position(tp1=True, tp1_ts=SETTLE_1, remaining="0")
        self.assertEqual(accrued_funding_cost(pos, EVENTS, MARKS, SETTLE_2),
                         Decimal("10.00"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
