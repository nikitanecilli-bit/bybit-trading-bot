"""Tests for chronological shared-equity portfolio replay."""
import unittest

from research_v15.portfolio_replay import replay_portfolio


def trade(entry_ts, exit_ts, pnl=10.0, symbol_side="long"):
    return {
        "side": symbol_side,
        "entry_ts": entry_ts,
        "exit_ts": exit_ts,
        "entry_price": 100.0,
        "exit_price": 101.0,
        "qty": 1.0,
        "initial_risk_usdt": 1.0,
        "net_pnl": pnl,
        "exit_reason": "test",
    }


class PortfolioReplayTests(unittest.TestCase):
    def test_reconciles_shared_equity_and_pnl(self):
        results = [
            {"symbol": "AAAUSDT", "trades": [trade(1, 2, 10)]},
            {"symbol": "BBBUSDT", "trades": [trade(3, 4, -5)]},
        ]
        result = replay_portfolio(results, starting_equity=10_000, risk_pct=0.01, max_portfolio_risk_pct=0.03)
        self.assertEqual(result["candidate_trades"], 2)
        self.assertEqual(result["accepted_trades"], 2)
        self.assertEqual(result["rejected_trades"], 0)
        self.assertAlmostEqual(result["net_pnl"], result["realized_pnl_sum"])
        self.assertAlmostEqual(result["reconciliation_error"], 0)

    def test_simultaneous_entries_obey_aggregate_risk_cap(self):
        results = [
            {"symbol": "AAAUSDT", "trades": [trade(1, 10, 10)]},
            {"symbol": "BBBUSDT", "trades": [trade(1, 10, 10)]},
            {"symbol": "CCCUSDT", "trades": [trade(1, 10, 10)]},
            {"symbol": "DDDUSDT", "trades": [trade(1, 10, 10)]},
        ]
        result = replay_portfolio(results, starting_equity=10_000, risk_pct=0.01, max_portfolio_risk_pct=0.025)
        self.assertEqual(result["accepted_trades"], 4)
        self.assertEqual(result["rejected_trades"], 0)
        self.assertTrue(all(t["portfolio_allocation_factor"] < 1 for t in result["accepted"]))
        self.assertLessEqual(
            sum(t["risk_usdt"] for t in result["accepted"]),
            250.0 + 1e-8,
        )

    def test_releases_risk_after_positions_exit(self):
        results = [
            {"symbol": "AAAUSDT", "trades": [trade(1, 2, 10)]},
            {"symbol": "BBBUSDT", "trades": [trade(3, 4, 10)]},
        ]
        result = replay_portfolio(results, starting_equity=10_000, risk_pct=0.01, max_portfolio_risk_pct=0.015)
        self.assertEqual(result["accepted_trades"], 2)
        self.assertEqual(result["rejected_trades"], 0)

    def test_invalid_trade_data_rejected(self):
        with self.assertRaises(ValueError):
            replay_portfolio([{"symbol": "BAD", "trades": [trade(2, 1)]}])

    def test_empty_input_is_valid(self):
        result = replay_portfolio([])
        self.assertEqual(result["candidate_trades"], 0)
        self.assertEqual(result["net_pnl"], 0)
        self.assertEqual(result["reconciliation_error"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
