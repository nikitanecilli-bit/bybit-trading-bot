"""End-to-end v14 mark-to-market funding regression tests."""
import importlib.util
import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).with_name("Bybit_Trading_Engine_v14_research.py")
spec = importlib.util.spec_from_file_location("research_engine_funding_mtm", ENGINE_PATH)
engine_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine_mod
spec.loader.exec_module(engine_mod)


def make_engine(funding=True):
    engine = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    engine.funding_dir = "/funding" if funding else None
    engine.funding_by_symbol = {
        "BTCUSDT": [{"ts": 2_000, "rate": 0.01}]
    } if funding else {}
    engine._funding_mark_prices = {"BTCUSDT": {2_000: 100.0}} if funding else {}
    engine.open_positions = {
        "BTCUSDT": engine_mod.OpenPositionState(
            trade_id="mtm-funding", symbol="BTCUSDT", direction="long",
            strategy="test", entry_ts=1_000, entry_price=100.0,
            stop_price=95.0, tp1_price=110.0, tp2_price=120.0,
            initial_stop_dist=5.0, size_usdt=1_000.0, risk_usdt=50.0,
            order_type="market",
        )
    }
    engine._intrabar_risk_marks = {"BTCUSDT": 100.0}
    engine._last_mark_prices = {"BTCUSDT": 100.0}
    engine._intrabar_risk_marks_ts = 2_000
    return engine


def test_mark_to_market_deducts_accrued_funding_before_position_close():
    with_funding = engine_mod.UnifiedQuantEngine._unrealized_pnl_at_marks(
        make_engine(True), 2_000
    )
    without_funding = engine_mod.UnifiedQuantEngine._unrealized_pnl_at_marks(
        make_engine(False), 2_000
    )
    assert round(without_funding - with_funding, 2) == 10.0


def test_mark_to_market_does_not_charge_future_settlement():
    engine = make_engine(True)
    value = engine_mod.UnifiedQuantEngine._unrealized_pnl_at_marks(engine, 1_999)
    baseline = engine_mod.UnifiedQuantEngine._unrealized_pnl_at_marks(make_engine(False), 1_999)
    assert value == baseline


def test_mark_to_market_fails_closed_without_exact_settlement_mark():
    engine = make_engine(True)
    engine._funding_mark_prices = {"BTCUSDT": {}}
    try:
        engine_mod.UnifiedQuantEngine._unrealized_pnl_at_marks(engine, 2_000)
    except RuntimeError as exc:
        assert "Missing exact candle-boundary mark proxy" in str(exc)
    else:
        raise AssertionError("Missing settlement mark must not silently omit funding")


def test_tp1_application_records_conservative_candle_close_boundary():
    pos = engine_mod.OpenPositionState(
        trade_id="tp1-ts", symbol="BTCUSDT", direction="long",
        strategy="test", entry_ts=1_000, entry_price=100.0,
        stop_price=95.0, tp1_price=110.0, tp2_price=120.0,
        initial_stop_dist=5.0, size_usdt=1_000.0, risk_usdt=50.0,
        order_type="market",
    )
    engine_mod.UnifiedQuantEngine._apply_tp1(pos, 3_600_000)
    assert pos.tp1_hit is True
    assert pos.tp1_ts_ms == 3_600_000
    assert pos.remaining_fraction == 0.5


if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
