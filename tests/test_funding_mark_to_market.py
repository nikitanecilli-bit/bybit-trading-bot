"""End-to-end v14 mark-to-market funding regression tests."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import importlib.util
import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).resolve().parent.parent / "Bybit_Trading_Engine_v14_research.py"
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
    engine._intrabar_mtm_marks = {"BTCUSDT": 100.0}
    engine._last_mark_prices = {"BTCUSDT": 100.0}
    engine._intrabar_risk_marks_ts = 2_000
    engine._intrabar_mtm_marks_ts = 2_000
    engine._persist = lambda: None
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


def test_funding_can_trigger_daily_stop_before_position_close():
    engine = make_engine(True)
    engine.cfg = engine_mod.BotConfig(
        timeframe="1h", capital_usdt=10_000.0, daily_stop_loss_pct=0.05
    )
    engine.risk_mgr = engine_mod.AdaptiveRiskManager(engine.cfg)
    engine.tg = type("Notifier", (), {"send_message": lambda self, message: None})()
    engine_mod.UnifiedQuantEngine._update_mark_to_market(engine, 2_000)
    assert engine.risk_mgr.daily_stop_triggered is True


def test_without_funding_the_same_position_does_not_hit_tight_daily_stop():
    engine = make_engine(False)
    engine.cfg = engine_mod.BotConfig(
        timeframe="1h", capital_usdt=10_000.0, daily_stop_loss_pct=0.05
    )
    engine.risk_mgr = engine_mod.AdaptiveRiskManager(engine.cfg)
    engine.tg = type("Notifier", (), {"send_message": lambda self, message: None})()
    engine_mod.UnifiedQuantEngine._update_mark_to_market(engine, 2_000)
    assert engine.risk_mgr.daily_stop_triggered is False


def test_legacy_limit_position_uses_maker_tp1_fee_fallback_in_mtm():
    engine = make_engine(False)
    pos = engine.open_positions["BTCUSDT"]
    pos.order_type = "limit"
    pos.maker_exits = None  # legacy/restored state predating explicit maker_exits
    pos.tp1_hit = True
    pos.tp1_ts_ms = 1_500
    pos.remaining_fraction = 0.5
    pos.realized_tp1_gross_usdt = 50.0
    value = engine_mod.UnifiedQuantEngine._unrealized_pnl_at_marks(engine, 2_000)
    # Entry maker fee 0.20 + TP1 maker fee 0.11 + remaining taker close
    # fee/slippage 0.3875. A falsey-None fallback would overcharge TP1.
    assert abs(value - 49.3025) < 1e-9


def test_explicit_taker_tp1_override_is_preserved_in_mtm():
    engine = make_engine(False)
    pos = engine.open_positions["BTCUSDT"]
    pos.order_type = "limit"
    pos.maker_exits = False
    pos.tp1_hit = True
    pos.tp1_ts_ms = 1_500
    pos.remaining_fraction = 0.5
    pos.realized_tp1_gross_usdt = 50.0
    value = engine_mod.UnifiedQuantEngine._unrealized_pnl_at_marks(engine, 2_000)
    # Entry maker fee 0.20 + TP1 taker fee/slippage 0.42625
    # + remaining taker fee/slippage 0.3875.
    assert abs(value - 48.98625) < 1e-9


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
    tests = [(name, value) for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for name, test in tests:
        test()
        print("PASS", name)
    print(f"{len(tests)}/{len(tests)} tests passed")
