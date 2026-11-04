import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from exchange_execution_identity import (
    ExchangeExecutionIdentity,
    ExchangeOrderIdentity,
    ExchangePositionIdentity,
    ExecutionIdentityError,
)


class ExchangeExecutionIdentityTests(unittest.TestCase):
    def test_position_identity_round_trips_exact_decimal_strings(self):
        value = ExchangePositionIdentity(
            category="linear", settle_coin="USDT", symbol="BTCUSDT",
            position_idx=1, position_mode="hedge", side="Buy",
            qty="0.00100", avg_price="68000.25", entry_order_id="order-1",
            entry_order_link_id="bot-entry-1",
        )
        self.assertEqual(ExchangePositionIdentity.from_dict(value.to_dict()), value)
        self.assertEqual(value.qty, "0.00100")

    def test_position_mode_and_index_must_agree(self):
        with self.assertRaisesRegex(ExecutionIdentityError, "conflicts"):
            ExchangePositionIdentity(
                "linear", "USDT", "BTCUSDT", 0, "hedge", "Buy",
                "1", "100", "order-1",
            )

    def test_position_qty_cannot_be_inferred_or_missing(self):
        with self.assertRaises(ExecutionIdentityError):
            ExchangePositionIdentity(
                "linear", "USDT", "BTCUSDT", 0, "one_way", "Buy",
                "", "100", "order-1",
            )

    def test_execution_identity_requires_unique_exchange_execution_id(self):
        value = ExchangeExecutionIdentity(
            "exec-1", "order-1", "bot-entry-1", "BTCUSDT",
            "Buy", "0.0005", "68000", 1_800_000_000_000, "-0.012",
        )
        self.assertEqual(ExchangeExecutionIdentity.from_dict(value.to_dict()), value)

    def test_execution_rejects_non_positive_fill_qty(self):
        with self.assertRaises(ExecutionIdentityError):
            ExchangeExecutionIdentity(
                "exec-1", "order-1", "", "BTCUSDT",
                "Buy", "0", "68000", 1_800_000_000_000,
            )

    def test_order_identity_checks_partial_fill_accounting(self):
        value = ExchangeOrderIdentity(
            "order-1", "bot-stop-1", "BTCUSDT", "Sell", 0,
            "1.0", "0.4", "0.6", "PartiallyFilled",
            True, True, "65000",
        )
        self.assertEqual(ExchangeOrderIdentity.from_dict(value.to_dict()), value)

    def test_order_identity_rejects_inconsistent_leaves_and_fills(self):
        with self.assertRaisesRegex(ExecutionIdentityError, "inconsistent"):
            ExchangeOrderIdentity(
                "order-1", "", "BTCUSDT", "Sell", 0,
                "1.0", "0.7", "0.6", "PartiallyFilled",
                True, True,
            )

    def test_unknown_fields_fail_closed(self):
        value = {
            "category": "linear", "settle_coin": "USDT", "symbol": "BTCUSDT",
            "position_idx": 0, "position_mode": "one_way", "side": "Buy",
            "qty": "1", "avg_price": "100", "entry_order_id": "order-1",
            "entry_order_link_id": "", "unexpected": "value",
        }
        with self.assertRaisesRegex(ExecutionIdentityError, "unknown"):
            ExchangePositionIdentity.from_dict(value)


if __name__ == "__main__":
    unittest.main()
