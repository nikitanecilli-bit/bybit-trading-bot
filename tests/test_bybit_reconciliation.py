"""Strict parser tests for read-only Bybit V5 reconciliation snapshots."""
import unittest
from decimal import Decimal

from bybit_reconciliation import (
    SnapshotValidationError,
    parse_active_order_pages,
    parse_execution_pages,
    parse_position_pages,
)


def page(rows, cursor=""):
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {"list": rows, "nextPageCursor": cursor},
        "time": 1_800_000_000_000,
    }


class BybitReconciliationParserTests(unittest.TestCase):
    def test_position_pages_require_complete_cursor_chain_and_parse_hedge_sides(self):
        first = page([{
            "symbol": "BTCUSDT", "positionIdx": 1, "side": "Buy",
            "size": "0.010", "avgPrice": "65000", "updatedTime": "1800000000000",
            "positionStatus": "Normal",
        }], "cursor-1")
        second = page([{
            "symbol": "BTCUSDT", "positionIdx": 2, "side": "Sell",
            "size": "0.020", "avgPrice": "64000", "updatedTime": "1800000000100",
            "positionStatus": "Normal",
        }])
        positions = parse_position_pages([("", first), ("cursor-1", second)])
        self.assertEqual(len(positions), 2)
        self.assertEqual([p.position_idx for p in positions], [1, 2])
        self.assertEqual(positions[0].size, Decimal("0.010"))
        self.assertEqual(positions[1].side, "Sell")

    def test_position_empty_zero_size_row_is_ignored(self):
        positions = parse_position_pages([("", page([{
            "symbol": "BTCUSDT", "positionIdx": 0, "side": "",
            "size": "0", "avgPrice": "", "updatedTime": "1800000000000",
            "positionStatus": "Normal",
        }]))])
        self.assertEqual(positions, ())

    def test_position_duplicate_symbol_and_index_is_rejected(self):
        row = {
            "symbol": "BTCUSDT", "positionIdx": 0, "side": "Buy",
            "size": "1", "avgPrice": "100", "updatedTime": "1800000000000",
            "positionStatus": "Normal",
        }
        with self.assertRaisesRegex(SnapshotValidationError, "duplicate position"):
            parse_position_pages([("", page([row, row]))])

    def test_incomplete_or_discontinuous_pagination_is_rejected(self):
        first = page([], "cursor-1")
        with self.assertRaisesRegex(SnapshotValidationError, "incomplete"):
            parse_position_pages([("", first)])
        with self.assertRaisesRegex(SnapshotValidationError, "discontinuous"):
            parse_position_pages([("wrong-cursor", page([]))])

    def test_bybit_error_response_is_not_treated_as_empty_account(self):
        payload = {"retCode": 10006, "retMsg": "rate limit", "result": {"list": [], "nextPageCursor": ""}}
        with self.assertRaisesRegex(SnapshotValidationError, "retCode"):
            parse_position_pages([("", payload)])

    def test_active_order_parser_preserves_partial_fill_quantities(self):
        order = {
            "orderId": "order-1", "orderLinkId": "bot-1", "symbol": "BTCUSDT",
            "side": "Buy", "qty": "10", "leavesQty": "4", "cumExecQty": "6",
            "orderStatus": "PartiallyFilled", "createdTime": "1800000000000",
            "updatedTime": "1800000000100", "positionIdx": 1,
        }
        orders = parse_active_order_pages([("", page([order]))])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].leaves_qty, Decimal("4"))
        self.assertEqual(orders[0].cum_exec_qty, Decimal("6"))
        self.assertEqual(orders[0].position_idx, 1)

    def test_active_order_inconsistent_quantities_are_rejected(self):
        order = {
            "orderId": "order-1", "symbol": "BTCUSDT", "side": "Buy",
            "qty": "10", "leavesQty": "7", "cumExecQty": "6",
            "orderStatus": "PartiallyFilled", "createdTime": "1800000000000",
            "updatedTime": "1800000000100",
        }
        with self.assertRaisesRegex(SnapshotValidationError, "inconsistent"):
            parse_active_order_pages([("", page([order]))])

    def test_duplicate_order_id_is_rejected(self):
        order = {
            "orderId": "order-1", "symbol": "BTCUSDT", "side": "Buy",
            "qty": "10", "leavesQty": "10", "cumExecQty": "0",
            "orderStatus": "New", "createdTime": "1800000000000",
            "updatedTime": "1800000000100",
        }
        with self.assertRaisesRegex(SnapshotValidationError, "duplicate orderId"):
            parse_active_order_pages([("", page([order, order]))])

    def test_execution_parser_allows_multiple_fills_for_one_order(self):
        rows = [
            {"execId": "exec-2", "orderId": "order-1", "symbol": "BTCUSDT",
             "execType": "Trade", "execTime": "1800000000200", "side": "Buy",
             "execQty": "0.2", "execPrice": "65000", "execFee": "0.1"},
            {"execId": "exec-1", "orderId": "order-1", "symbol": "BTCUSDT",
             "execType": "Trade", "execTime": "1800000000100", "side": "Buy",
             "execQty": "0.3", "execPrice": "64900", "execFee": "0.1"},
        ]
        executions = parse_execution_pages([("", page(rows))])
        self.assertEqual([x.exec_id for x in executions], ["exec-1", "exec-2"])
        self.assertEqual(sum(x.exec_qty for x in executions), Decimal("0.5"))

    def test_duplicate_execution_id_is_rejected(self):
        row = {"execId": "exec-1", "orderId": "order-1", "symbol": "BTCUSDT",
               "execType": "Trade", "execTime": "1800000000100", "side": "Buy",
               "execQty": "0.1", "execPrice": "65000", "execFee": "0.1"}
        with self.assertRaisesRegex(SnapshotValidationError, "duplicate execId"):
            parse_execution_pages([("", page([row, row]))])

    def test_funding_execution_can_have_no_trade_side_or_price(self):
        row = {"execId": "fund-1", "orderId": "", "symbol": "BTCUSDT",
               "execType": "Funding", "execTime": "1800000000100", "side": "",
               "execQty": "", "execPrice": "", "execFee": "-0.25"}
        executions = parse_execution_pages([("", page([row]))])
        self.assertEqual(executions[0].exec_type, "Funding")
        self.assertIsNone(executions[0].side)
        self.assertEqual(executions[0].exec_fee, Decimal("-0.25"))

    def test_trade_execution_requires_positive_quantity_price_and_side(self):
        row = {"execId": "exec-1", "orderId": "order-1", "symbol": "BTCUSDT",
               "execType": "Trade", "execTime": "1800000000100", "side": "Buy",
               "execQty": "0", "execPrice": "65000", "execFee": "0.1"}
        with self.assertRaisesRegex(SnapshotValidationError, "Trade execution requires"):
            parse_execution_pages([("", page([row]))])


if __name__ == "__main__":
    unittest.main()
