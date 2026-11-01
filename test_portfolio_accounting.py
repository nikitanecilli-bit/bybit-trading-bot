"""Deterministic accounting and portfolio-risk regression tests for v14 research engine."""
import importlib.util
import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).with_name("Bybit_Trading_Engine_v14_research.py")
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
