"""Deterministic accounting and portfolio-risk regression tests for v14 research engine."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import importlib.util
import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).resolve().parent.parent / "Bybit_Trading_Engine_v14_research.py"
spec = importlib.util.spec_from_file_location("research_engine_accounting", ENGINE_PATH)
engine_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine_mod
spec.loader.exec_module(engine_mod)


def make_position(symbol="BTCUSDT", direction="long", entry=100.0, size=1000.0,
                  remaining=1.0, tp1_hit=False, tp1_gross=0.0, order_type="market",
                  maker_exits=False):
    return engine_mod.OpenPositionState(
        trade_id=f"T-{symbol}", symbol=symbol, direction=direction, strategy="test",
        entry_ts=1_800_000_000_000, entry_price=entry, stop_price=95.0 if direction == "long" else 105.0,
        tp1_price=106.0 if direction == "long" else 94.0,
        tp2_price=112.0 if direction == "long" else 88.0,
        initial_stop_dist=5.0, size_usdt=size, risk_usdt=50.0,
        order_type=order_type, maker_exits=maker_exits, tp1_hit=tp1_hit,
        realized_tp1_gross_usdt=tp1_gross, remaining_fraction=remaining,
        equity_at_entry=10_000.0,
    )


def make_engine():
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = engine_mod.BotConfig(capital_usdt=10_000.0, timeframe="1h")
    e.risk_mgr = engine_mod.AdaptiveRiskManager(e.cfg)
    e.open_positions = {}
    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e.closed_trades = []
    e._persist = lambda: None
    e.tg = type("TelegramSpy", (), {"send_message": staticmethod(lambda *_: None)})()
    return e


def test_mark_to_market_equity_equals_realized_plus_unrealized():
    e = make_engine()
    e.open_positions["BTCUSDT"] = make_position(size=2_000.0)
    e._last_mark_prices["BTCUSDT"] = 103.0
    unrealized = e._unrealized_pnl_at_marks()
    e.risk_mgr.mark_to_market(unrealized, 1_800_000_000_000)
    assert e.risk_mgr.current_equity == round(
        e.risk_mgr.realized_equity + e.risk_mgr.unrealized_pnl, 4
    )
    assert e.risk_mgr.current_equity < e.risk_mgr.realized_equity + 60.0


def test_tp1_partial_position_mark_includes_realized_leg_and_remaining_leg():
    e = make_engine()
    # TP1 has realized 1% on 50% notional; remaining 50% is marked 2% above entry.
    e.open_positions["BTCUSDT"] = make_position(
        size=2_000.0, remaining=0.5, tp1_hit=True, tp1_gross=10.0,
    )
    e._last_mark_prices["BTCUSDT"] = 102.0
    value = e._unrealized_pnl_at_marks()
    expected_gross = 10.0 + 2_000.0 * 0.5 * 0.02
    expected_costs = (
        2_000.0 * engine_mod.TAKER_FEE
        + 2_000.0 * engine_mod.TAKER_SLIP
        + 2_000.0 * engine_mod.TP1_FRACTION * engine_mod.TAKER_FEE
        + 2_000.0 * engine_mod.TP1_FRACTION * engine_mod.TAKER_SLIP
        + 2_000.0 * 0.5 * (engine_mod.TAKER_FEE + engine_mod.TAKER_SLIP)
    )
    assert abs(value - (expected_gross - expected_costs)) < 1e-8


def test_portfolio_risk_budget_caps_new_position_size():
    cfg = engine_mod.BotConfig(
        capital_usdt=10_000.0, max_risk_trade_pct=1.0,
        max_portfolio_risk_pct=2.0, leverage_val=5.0, max_concurrent_positions=2,
    )
    risk = engine_mod.AdaptiveRiskManager(cfg)
    size, estimated_risk = risk.calculate_position_size(
        100.0, 95.0, order_type="market", risk_budget_usdt=37.0,
    )
    assert estimated_risk <= 37.0
    assert size > 0


def test_zero_or_negative_remaining_portfolio_budget_rejects_position():
    cfg = engine_mod.BotConfig(capital_usdt=10_000.0)
    risk = engine_mod.AdaptiveRiskManager(cfg)
    assert risk.calculate_position_size(100.0, 95.0, risk_budget_usdt=0.0) == (0.0, 0.0)
    assert risk.calculate_position_size(100.0, 95.0, risk_budget_usdt=-1.0) == (0.0, 0.0)


def test_long_and_short_unrealized_pnl_have_opposite_signs():
    e = make_engine()
    e.open_positions["BTCUSDT"] = make_position(direction="long", size=1_000.0)
    e.open_positions["ETHUSDT"] = make_position(
        symbol="ETHUSDT", direction="short", size=1_000.0,
    )
    e._last_mark_prices.update({"BTCUSDT": 101.0, "ETHUSDT": 101.0})
    both = e._unrealized_pnl_at_marks()
    e.open_positions.pop("ETHUSDT")
    long_only = e._unrealized_pnl_at_marks()
    assert both < long_only
    assert long_only > 0


def test_close_trade_reconciles_net_pnl_fees_slippage_and_realized_equity():
    e = make_engine()
    pos = make_position(size=1_000.0, order_type="market", maker_exits=False)
    e.open_positions["BTCUSDT"] = pos
    e._last_mark_prices["BTCUSDT"] = 110.0
    gross = 1_000.0 * (110.0 - 100.0) / 100.0
    expected_fees = 1_000.0 * engine_mod.TAKER_FEE + 1_000.0 * engine_mod.TAKER_FEE
    expected_slippage = 1_000.0 * engine_mod.TAKER_SLIP + 1_000.0 * engine_mod.TAKER_SLIP

    e._close_position(
        pos, exit_price=110.0, exit_reason="take_profit",
        exit_ts=1_800_003_600_000, mae_r=0.0, mfe_r=2.0,
    )

    trade = e.closed_trades[-1]
    assert trade.gross_pnl == round(gross, 2)
    assert trade.exchange_fees_usdt == round(expected_fees, 2)
    assert trade.slippage_cost_usdt == round(expected_slippage, 2)
    assert trade.pnl_usdt == round(gross - expected_fees - expected_slippage, 2)
    assert e.risk_mgr.realized_equity == round(10_000.0 + trade.pnl_usdt, 4)
    assert e.risk_mgr.current_equity == round(
        e.risk_mgr.realized_equity + e.risk_mgr.unrealized_pnl, 4
    )
    assert "BTCUSDT" not in e.open_positions


def run_simultaneous_entries(order):
    e = make_engine()
    e.cfg.max_portfolio_risk_pct = 2.0
    e.cfg.max_risk_trade_pct = 1.0
    e.cfg.max_concurrent_positions = 3
    e.risk_mgr.cfg = e.cfg
    for symbol in order:
        e.pending[symbol] = {
            "direction": "long", "entry_price": 100.0, "order_type": "market",
            "strategy": "simultaneous-test", "stop_dist": 5.0,
        }
    bar = engine_mod.Candle(
        ts=1_800_000_000_000, open=100.0, high=101.0,
        low=99.0, close=100.5, volume=10.0,
    )
    e._prepare_pending_entry_risk_budgets()
    for symbol in order:
        e._try_fill_pending(symbol, bar)
    return e


def test_simultaneous_entries_share_risk_budget_independent_of_symbol_order():
    first_order = run_simultaneous_entries(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    reversed_order = run_simultaneous_entries(["SOLUSDT", "ETHUSDT", "BTCUSDT"])
    assert set(first_order.open_positions) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
    assert set(reversed_order.open_positions) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
    first_risk = sum(p.risk_usdt for p in first_order.open_positions.values())
    reverse_risk = sum(p.risk_usdt for p in reversed_order.open_positions.values())
    assert first_risk <= 200.0
    assert reverse_risk <= 200.0
    assert abs(first_risk - reverse_risk) < 0.01


def test_position_slot_priority_uses_signal_strength_not_iteration_order():
    def selected(order):
        e = make_engine()
        e.cfg.max_concurrent_positions = 2
        e.pending = {
            "BTCUSDT": {"direction": "long", "entry_price": 100.0, "order_type": "market", "strategy": "test", "stop_dist": 5.0, "vol_ratio": 1.8},
            "ETHUSDT": {"direction": "long", "entry_price": 100.0, "order_type": "market", "strategy": "test", "stop_dist": 5.0, "vol_ratio": 2.4},
            "SOLUSDT": {"direction": "long", "entry_price": 100.0, "order_type": "market", "strategy": "test", "stop_dist": 5.0, "vol_ratio": 2.1},
        }
        bar = engine_mod.Candle(ts=1_800_000_000_000, open=100.0, high=101.0, low=99.0, close=100.5, volume=10.0)
        e._prepare_pending_entry_risk_budgets()
        for symbol in order:
            e._try_fill_pending(symbol, bar)
        return set(e.open_positions)
    assert selected(["BTCUSDT", "ETHUSDT", "SOLUSDT"]) == {"ETHUSDT", "SOLUSDT"}
    assert selected(["SOLUSDT", "ETHUSDT", "BTCUSDT"]) == {"ETHUSDT", "SOLUSDT"}


def test_stopped_long_mae_uses_stop_fill_and_does_not_count_later_wick_as_mfe():
    e = make_engine()
    pos = make_position(direction="long", entry=100.0, size=1_000.0)
    e.open_positions["BTCUSDT"] = pos
    captured = {}
    e._close_position = lambda p, px, reason, ts, mae, mfe: captured.update(
        exit_price=px, reason=reason, mae=mae, mfe=mfe
    )
    history = [
        engine_mod.Candle(ts=1_800_000_000_000, open=100, high=101, low=99, close=100, volume=10),
        engine_mod.Candle(ts=1_800_003_600_000, open=100, high=120, low=90, close=110, volume=10),
    ]
    e._manage_position("BTCUSDT", history, fill_bar=False, exit_ts=1_800_007_200_000)
    assert captured["exit_price"] == 95.0
    assert captured["mae"] == 1.0
    assert captured["mfe"] == 0.0


def test_stopped_short_mae_uses_stop_fill_and_does_not_count_later_wick_as_mfe():
    e = make_engine()
    pos = make_position(symbol="ETHUSDT", direction="short", entry=100.0, size=1_000.0)
    e.open_positions["ETHUSDT"] = pos
    captured = {}
    e._close_position = lambda p, px, reason, ts, mae, mfe: captured.update(
        exit_price=px, reason=reason, mae=mae, mfe=mfe
    )
    history = [
        engine_mod.Candle(ts=1_800_000_000_000, open=100, high=101, low=99, close=100, volume=10),
        engine_mod.Candle(ts=1_800_003_600_000, open=100, high=110, low=80, close=90, volume=10),
    ]
    e._manage_position("ETHUSDT", history, fill_bar=False, exit_ts=1_800_007_200_000)
    assert captured["exit_price"] == 105.0
    assert captured["mae"] == 1.0
    assert captured["mfe"] == 0.0
