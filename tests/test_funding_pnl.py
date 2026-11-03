"""Regression tests for funding cashflows included in net trade PnL."""
from pathlib import Path as _Path
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import importlib.util
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

ENGINE_PATH = Path(__file__).resolve().parent.parent / "Bybit_Trading_Engine_v14_research.py"
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


def test_funding_exactly_at_tp1_boundary_uses_full_position():
    e, pos = make_engine("long", 0.01, tp1=True)
    ts = pos.tp1_ts_ms
    e.funding_by_symbol["BTCUSDT"][0]["ts"] = ts
    e._funding_mark_prices["BTCUSDT"][ts] = 100.0
    record = close(e, pos)
    assert record.funding_cost_usdt == 10.0


def test_funding_exactly_at_exit_boundary_is_included():
    e, pos = make_engine("long", 0.01)
    ts = 1_800_001_000_000
    e.funding_by_symbol["BTCUSDT"][0]["ts"] = ts
    e._funding_mark_prices["BTCUSDT"][ts] = 100.0
    record = close(e, pos)
    assert record.funding_cost_usdt == 10.0


def test_funding_at_entry_boundary_is_conservatively_charged():
    e, pos = make_engine("long", 0.01)
    e.funding_by_symbol["BTCUSDT"][0]["ts"] = pos.entry_ts
    e._funding_mark_prices["BTCUSDT"][pos.entry_ts] = 100.0
    record = close(e, pos)
    assert record.funding_cost_usdt == 10.0


def test_funding_strictly_before_entry_is_not_charged():
    e, pos = make_engine("long", 0.01)
    e.funding_by_symbol["BTCUSDT"][0]["ts"] = pos.entry_ts - 1
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



def test_mark_price_history_loader_uses_hourly_candle_open():
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e._funding_mark_prices = {}
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "BTCUSDT.csv"
        path.write_text(
            "symbol,timestamp_ms,time_utc,open,high,low,close\n"
            "BTCUSDT,1800000000000,2030-01-15T08:00:00Z,101.25,102,100,101.5\n",
            encoding="utf-8",
        )
        e._load_mark_price_history(directory)
    assert e._funding_mark_prices["BTCUSDT"][1_800_000_000_000] == 101.25


def test_mark_price_history_loader_rejects_duplicate_timestamps():
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e._funding_mark_prices = {}
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "BTCUSDT.csv"
        path.write_text(
            "symbol,timestamp_ms,open\n"
            "BTCUSDT,1800000000000,101.25\n"
            "BTCUSDT,1800000000000,101.5\n",
            encoding="utf-8",
        )
        try:
            e._load_mark_price_history(directory)
        except ValueError as exc:
            assert "duplicate mark-price timestamp" in str(exc)
        else:
            raise AssertionError("Duplicate mark-price timestamps must be rejected")


def test_funding_history_loader_rejects_empty_symbol_file():
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.funding_by_symbol = {}
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "BTCUSDT.csv"
        path.write_text(
            "symbol,funding_timestamp_ms,funding_rate\n",
            encoding="utf-8",
        )
        try:
            e._load_funding_history(directory)
        except ValueError as exc:
            assert "no funding rows found" in str(exc)
        else:
            raise AssertionError("Empty funding history must be rejected")


def test_funding_history_loader_preserves_decimal_rate_precision():
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.funding_by_symbol = {}
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "BTCUSDT.csv"
        path.write_text(
            "symbol,funding_timestamp_ms,funding_rate\n"
            "BTCUSDT,1800000000000,0.0001234567890123456789\n",
            encoding="utf-8",
        )
        e._load_funding_history(directory)
    assert e.funding_by_symbol["BTCUSDT"][0]["rate"] == Decimal("0.0001234567890123456789")


def test_mark_price_history_loader_preserves_decimal_precision():
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e._funding_mark_prices = {}
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "BTCUSDT.csv"
        path.write_text(
            "symbol,timestamp_ms,open\n"
            "BTCUSDT,1800000000000,101.1234567890123456789\n",
            encoding="utf-8",
        )
        e._load_mark_price_history(directory)
    assert e._funding_mark_prices["BTCUSDT"][1_800_000_000_000] == Decimal("101.1234567890123456789")


if __name__ == "__main__":
    tests = [(name, value) for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for name, test in tests:
        test()
        print("PASS", name)
    print(f"{len(tests)}/{len(tests)} tests passed")
