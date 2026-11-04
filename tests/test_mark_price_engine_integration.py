"""End-to-end tests for Mark OHLC ingestion and isolated liquidation lifecycle."""
from pathlib import Path
import csv
import importlib.util
import sys
import tempfile
from decimal import Decimal
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ENGINE_PATH = ROOT / "Bybit_Trading_Engine_v14_research.py"
spec = importlib.util.spec_from_file_location("research_engine_mark_liquidation", ENGINE_PATH)
em = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = em
spec.loader.exec_module(em)

from bybit_risk_tiers import RiskTier, RiskTierHistory, RiskTierSnapshot


def make_position(symbol="BTCUSDT", direction="short", entry=99_000.0,
                  stop=100_000.0, size=99_000.0):
    return em.OpenPositionState(
        trade_id="T-MARK-1", symbol=symbol, direction=direction, strategy="test",
        entry_ts=1_800_000_000_000, entry_price=entry, stop_price=stop,
        tp1_price=entry - 1_000 if direction == "short" else entry + 1_000,
        tp2_price=entry - 2_000 if direction == "short" else entry + 2_000,
        initial_stop_dist=1_000.0, size_usdt=size, risk_usdt=1_000.0,
        order_type="market", equity_at_entry=10_000.0, leverage=50.0,
    )


def make_risk_history(as_of_ts):
    tiers = (
        RiskTier("BTCUSDT", 1, Decimal("100000"), Decimal("0.005"),
                 Decimal("0.01"), Decimal("100"), Decimal("0"), True),
        RiskTier("BTCUSDT", 2, Decimal("500000"), Decimal("0.10"),
                 Decimal("0.02"), Decimal("50"), Decimal("9500"), False),
    )
    return RiskTierHistory([RiskTierSnapshot(
        fetched_at="2027-01-15T00:00:00Z", fetched_at_ms=as_of_ts - 1,
        category="linear", tiers_by_symbol={"BTCUSDT": tiers},
    )])


def make_engine():
    engine = em.UnifiedQuantEngine.__new__(em.UnifiedQuantEngine)
    engine.cfg = em.BotConfig(capital_usdt=10_000.0, timeframe="1h", leverage_val=50.0)
    engine.risk_tier_history = None
    engine.max_risk_tier_age_ms = 30 * 24 * 60 * 60 * 1000
    engine.liquidation_model_enabled = False
    engine.funding_dir = None
    engine.funding_by_symbol = {}
    engine._funding_mark_prices = {}
    engine._mark_price_candles = {}
    engine._last_mark_prices = {}
    engine._intrabar_risk_marks = {}
    engine._intrabar_risk_marks_ts = None
    engine._intrabar_mtm_marks = {}
    engine._intrabar_mtm_marks_ts = None
    engine._intrabar_liquidation_exits = {}
    engine.open_positions = {}
    engine._persist = lambda: None
    engine.risk_mgr = SimpleNamespace(kill_switch_triggered=False)
    engine._close_position = lambda *args: setattr(engine, "closed_call", args)
    return engine


import unittest


class MarkPriceEngineIntegrationTests(unittest.TestCase):
    def test_loader_preserves_full_mark_ohlc(self):
        engine = make_engine()
        engine.liquidation_model_enabled = True
        engine.funding_by_symbol = {"BTCUSDT": []}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "BTCUSDT.csv")
            path.write_text(
                "symbol,timestamp_ms,open,high,low,close\n"
                "BTCUSDT,1800000000000,99000,100450,98500,100000\n",
                encoding="utf-8",
            )
            engine._load_mark_price_history(tmp)
        candle = engine._mark_price_candles["BTCUSDT"][1_800_000_000_000]
        assert candle.high == Decimal("100450")
        assert candle.low == Decimal("98500")
        assert engine._funding_mark_prices["BTCUSDT"][1_800_000_000_000] == Decimal("99000")

    def test_liquidation_mode_rejects_open_only_legacy_mark_archive(self):
        engine = make_engine()
        engine.liquidation_model_enabled = True
        engine.funding_by_symbol = {"BTCUSDT": []}
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "BTCUSDT.csv").write_text(
                "symbol,timestamp_ms,open\nBTCUSDT,1800000000000,99000\n",
                encoding="utf-8",
            )
            try:
                engine._load_mark_price_history(tmp)
            except ValueError as exc:
                assert "requires timestamp_ms,open,high,low,close" in str(exc)
            else:
                raise AssertionError("open-only Mark archive must be rejected for liquidation-aware replay")

    def test_liquidation_uses_position_entry_leverage_not_hot_reloaded_config(self):
        engine = make_engine()
        pos = make_position()
        ts = pos.entry_ts
        close_ts = ts + 3_600_000
        engine.liquidation_model_enabled = True
        engine.cfg.leverage_val = 10.0
        engine.risk_tier_history = make_risk_history(close_ts)
        engine._mark_price_candles = {"BTCUSDT": {
            ts: em.MarkPriceCandle(
                ts, Decimal("99000"), Decimal("100450"),
                Decimal("98500"), Decimal("100000"),
            )
        }}
        exit_price = engine._liquidation_exit_price(
            pos, em.Candle(ts, 99000, 100500, 98500, 100000, 1), close_ts,
        )
        self.assertEqual(exit_price, 100_980.0)

    def test_liquidation_requires_joined_market_state_when_both_histories_exist(self):
        engine = make_engine()
        pos = make_position()
        ts = pos.entry_ts
        close_ts = ts + 3_600_000
        engine.liquidation_model_enabled = True
        engine.risk_tier_history = make_risk_history(close_ts)
        engine.instrument_spec_history = object()
        engine.max_market_state_skew_ms = 0
        engine._mark_price_candles = {"BTCUSDT": {
            ts: em.MarkPriceCandle(
                ts, Decimal("99000"), Decimal("100450"),
                Decimal("98500"), Decimal("100000"),
            )
        }}
        with patch.object(
            em, "get_linear_market_state",
            side_effect=ValueError("max_snapshot_skew_ms must be a non-negative integer"),
        ) as joined:
            with self.assertRaisesRegex(ValueError, "max_snapshot_skew_ms"):
                engine._liquidation_exit_price(
                    pos, em.Candle(ts, 99000, 100500, 98500, 100000, 1), close_ts,
                )
        joined.assert_called_once()
        self.assertEqual(joined.call_args.kwargs["max_snapshot_skew_ms"], 0)

    def test_liquidation_margin_uses_only_remaining_share_of_pre_tp1_funding(self):
        engine = make_engine()
        pos = make_position(direction="long", stop=98_000.0)
        ts = pos.entry_ts
        close_ts = ts + 3_600_000
        pos.tp1_hit = True
        pos.tp1_ts_ms = ts + 2_000_000
        pos.remaining_fraction = 0.5
        engine.liquidation_model_enabled = True
        engine.risk_tier_history = make_risk_history(close_ts)
        engine.funding_dir = "/funding"
        engine.funding_by_symbol = {"BTCUSDT": [
            {"ts": ts + 1_000_000, "rate": "0.01"},
            {"ts": ts + 2_500_000, "rate": "0.01"},
        ]}
        engine._funding_mark_prices = {"BTCUSDT": {
            ts + 1_000_000: Decimal("99000"),
            ts + 2_500_000: Decimal("100000"),
        }}
        engine._mark_price_candles = {"BTCUSDT": {
            ts: em.MarkPriceCandle(
                ts, Decimal("99000"), Decimal("100450"),
                Decimal("98500"), Decimal("100000"),
            )
        }}
        observed = {}

        def capture_health(**kwargs):
            observed["funding_net_cost"] = kwargs["funding_net_cost"]
            return SimpleNamespace(liquidation_triggered=False)

        with patch.object(em, "evaluate_isolated_margin_health", side_effect=capture_health):
            engine._liquidation_exit_price(
                pos, em.Candle(ts, 99000, 100500, 98500, 100000, 1), close_ts,
            )

        # Pre-TP1 settlement is prorated to the 50% position still open;
        # post-TP1 settlement is already on the remaining 50% quantity.
        self.assertEqual(observed["funding_net_cost"], Decimal("995.00"))

    def test_liquidation_margin_uses_only_remaining_quantity_after_tp1(self):
        engine = make_engine()
        pos = make_position(direction="long", stop=98_000.0)
        pos.tp1_hit = True
        pos.tp1_ts_ms = pos.entry_ts + 2_000_000
        pos.remaining_fraction = 0.5
        engine.liquidation_model_enabled = True
        close_ts = pos.entry_ts + 3_600_000
        engine.risk_tier_history = make_risk_history(close_ts)
        engine._mark_price_candles = {"BTCUSDT": {
            pos.entry_ts: em.MarkPriceCandle(
                pos.entry_ts, Decimal("99000"), Decimal("100450"),
                Decimal("98500"), Decimal("100000"),
            )
        }}
        observed = {}

        def capture_health(**kwargs):
            observed["quantity"] = kwargs["quantity"]
            observed["tiers"] = kwargs["tiers"]
            return SimpleNamespace(liquidation_triggered=False)

        with patch.object(em, "evaluate_isolated_margin_health", side_effect=capture_health):
            engine._liquidation_exit_price(
                pos,
                em.Candle(pos.entry_ts, 99000, 100500, 98500, 100000, 1),
                close_ts,
            )

        self.assertEqual(observed["quantity"], Decimal("0.5"))
        self.assertEqual(observed["tiers"], engine.risk_tier_history.get_tiers("BTCUSDT", close_ts))

    def test_dynamic_mark_tier_shortfall_triggers_before_fixed_lp(self):
        engine = make_engine()
        pos = make_position()
        ts = pos.entry_ts
        close_ts = ts + 3_600_000
        engine.liquidation_model_enabled = True
        engine.risk_tier_history = make_risk_history(close_ts)
        engine._mark_price_candles = {"BTCUSDT": {
            ts: em.MarkPriceCandle(
                ts, Decimal("99000"), Decimal("100450"),
                Decimal("98500"), Decimal("100000"),
            )
        }}
        exit_price = engine._liquidation_exit_price(
            pos, em.Candle(ts, 99000, 100500, 98500, 100000, 1), close_ts,
        )
        assert exit_price == 100_980.0
        assert exit_price > 100_450.0

    def test_mark_liquidation_precedes_same_bar_last_price_stop(self):
        engine = make_engine()
        pos = make_position()
        ts = pos.entry_ts
        close_ts = ts + 3_600_000
        engine.liquidation_model_enabled = True
        engine.risk_tier_history = make_risk_history(close_ts)
        engine._mark_price_candles = {"BTCUSDT": {
            ts: em.MarkPriceCandle(
                ts, Decimal("99000"), Decimal("100450"),
                Decimal("98500"), Decimal("100000"),
            )
        }}
        engine.open_positions = {"BTCUSDT": pos}
        candle = em.Candle(ts, 99000, 100500, 98500, 100000, 1)
        engine._manage_position("BTCUSDT", [em.Candle(ts-3_600_000, 99000, 99500, 98500, 99000, 1), candle],
                                fill_bar=False, exit_ts=close_ts)
        assert engine.closed_call[1] == 100_980.0
        assert engine.closed_call[2] == "liquidation"

    def test_liquidation_close_does_not_charge_ordinary_exit_fee_or_slippage(self):
        engine = make_engine()
        pos = make_position()
        engine.cfg.bot_version = "test"
        engine.open_positions = {"BTCUSDT": pos}
        engine.closed_trades = []
        engine.risk_mgr.unrealized_pnl = 0.0
        engine.risk_mgr.register_closed_trade_pnl = lambda *_args: {}
        engine._unrealized_pnl_at_marks = lambda *_args: 0.0
        engine._persist = lambda: None
        engine._last_mark_prices = {"BTCUSDT": 100_980.0}
        engine.tg = SimpleNamespace(send_message=lambda *_args: None)
        engine._close_position = em.UnifiedQuantEngine._close_position.__get__(engine)
        engine._close_position(
            pos, exit_price=100_980.0, exit_reason="liquidation",
            exit_ts=pos.entry_ts + 3_600_000, mae_r=1.98, mfe_r=0.0,
        )
        trade = engine.closed_trades[-1]
        assert trade.exchange_fees_usdt == 54.45
        assert trade.slippage_cost_usdt == 22.28
        assert trade.exit_reason == "liquidation"

    def test_tp1_rejects_short_remainder_below_min_notional_at_tp2(self):
        pos = make_position(direction="short", entry=100.0, stop=105.0, size=100.0)
        pos.tp1_price = 90.0
        pos.tp2_price = 80.0
        pos.exchange_sized = True
        pos.contract_qty = "1.0"
        pos.remaining_contract_qty = "1.0"
        pos.qty_step = "0.1"
        pos.min_order_qty = "0.1"
        pos.min_notional_value = "45"

        # TP1 order is exactly at minNotional (0.5 * 90 = 45).
        # The remaining TP2 order would be below it (0.5 * 80 = 40),
        # although the old stop/entry-only check incorrectly accepted it.
        applied = em.UnifiedQuantEngine._apply_tp1(pos, 3_600_000)
        self.assertFalse(applied)
        self.assertFalse(pos.tp1_hit)
        self.assertEqual(pos.remaining_contract_qty, "1.0")

    def test_mark_price_mtm_is_separate_from_last_price_stop_mark(self):
        engine = make_engine()
        pos = make_position(direction="long", entry=100.0, stop=90.0, size=1_000.0)
        ts = pos.entry_ts
        engine.open_positions = {"BTCUSDT": pos}
        engine._mark_price_candles = {"BTCUSDT": {
            ts: em.MarkPriceCandle(
                ts, Decimal("100"), Decimal("102"), Decimal("95"), Decimal("101"),
            )
        }}
        trade = em.Candle(ts, 100, 103, 97, 102, 10)
        engine._prepare_portfolio_intrabar_marks({"BTCUSDT": trade})
        assert engine._intrabar_risk_marks["BTCUSDT"] == 97
        assert engine._intrabar_mtm_marks["BTCUSDT"] == 95
        assert engine._last_mark_prices["BTCUSDT"] == 101


if __name__ == "__main__":
    unittest.main(verbosity=2)
