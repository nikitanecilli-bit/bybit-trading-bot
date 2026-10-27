"""Regression tests for funding cashflows included in net trade PnL."""
import importlib.util
import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).with_name("Bybit_Trading_Engine_v14_research.py")
spec = importlib.util.spec_from_file_location("research_engine_funding", ENGINE_PATH)
engine_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine_mod
spec.loader.exec_module(engine_mod)


def make_engine(direction="long", rate=0.01, tp1=False):
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = engine_mod.BotConfig(timeframe="1h", capital_usdt=10_000.0)
    e.funding_dir = "/funding"
    e.funding_by_symbol = {"BTCUSDT": [{"ts": 1_800_000_000_000, "rate": rate}]}
    e._funding_mark_prices = {"BTCUSDT": {1_800_000_000_000: 100.0}}
    e.open_positions = {}
    e.closed_trades = []
    e._last_mark_prices = {}
    e._intrabar_risk_marks = {}
    e.risk_mgr = engine_mod.AdaptiveRiskManager(e.cfg)
    e.tg = type("Notifier", (), {"send_message": lambda self, message: None})()
    e._persist = lambda: None
    pos = engine_mod.OpenPositionState(
        trade_id="funding-test", symbol="BTCUSDT", direction=direction,
        strategy="test", entry_ts=1_799_999_000_000, entry_price=100.0,
        stop_price=95.0 if direction == "long" else 105.0,
        tp1_price=110.0 if direction == "long" else 90.0,
        tp2_price=120.0 if direction == "long" else 80.0,
        initial_stop_dist=5.0, size_usdt=1_000.0, risk_usdt=50.0,
        order_type="market",
    )
    if tp1:
        pos.tp1_hit = True
        pos.tp1_ts_ms = 1_799_999_500_000
        pos.remaining_fraction = 0.5
        pos.realized_tp1_gross_usdt = 50.0
    e.open_positions["BTCUSDT"] = pos
    return e, pos


def close(e, pos):
    engine_mod.UnifiedQuantEngine._close_position(
        e, pos, 100.0, "time_stop", 1_800_001_000_000, mae_r=0.0, mfe_r=0.0
    )
    return e.closed_trades[-1]


def test_long_pays_positive_funding_and_net_pnl_includes_it():
    e, pos = make_engine("long", 0.01)
    record = close(e, pos)
    assert record.funding_cost_usdt == 10.0
    assert record.pnl_usdt == round(record.gross_pnl - record.exchange_fees_usdt
                                     - record.slippage_cost_usdt - 10.0, 2)


def test_short_receives_positive_funding():
    e, pos = make_engine("short", 0.01)
    record = close(e, pos)
    assert record.funding_cost_usdt == -10.0
    assert record.pnl_usdt == round(record.gross_pnl - record.exchange_fees_usdt
                                     - record.slippage_cost_usdt + 10.0, 2)


def test_partial_tp1_reduces_notional_for_later_funding():
    e, pos = make_engine("long", 0.01, tp1=True)
    record = close(e, pos)
    assert record.funding_cost_usdt == 5.0


def test_funding_before_tp1_candle_close_uses_full_position():
    e, pos = make_engine("long", 0.01, tp1=True)
    # Settlement occurs after entry but before the conservative TP1 candle-close boundary.
    e.funding_by_symbol["BTCUSDT"][0]["ts"] = 1_799_999_400_000
    e._funding_mark_prices["BTCUSDT"][1_799_999_400_000] = 100.0
    record = close(e, pos)
    assert record.funding_cost_usdt == 10.0


def test_funding_before_entry_is_not_charged():
    e, pos = make_engine("long", 0.01)
    e.funding_by_symbol["BTCUSDT"][0]["ts"] = pos.entry_ts
    record = close(e, pos)
    assert record.funding_cost_usdt == 0.0


def test_missing_mark_proxy_fails_loudly():
    e, pos = make_engine("long", 0.01)
    e._funding_mark_prices = {"BTCUSDT": {}}
    try:
        close(e, pos)
    except RuntimeError as exc:
        assert "Missing exact candle-boundary mark proxy" in str(exc)
    else:
        raise AssertionError("missing mark proxy must not silently omit funding")
