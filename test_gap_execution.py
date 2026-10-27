"""Focused tests for next-bar entry behavior under gaps in the research engine copy."""
import importlib.util
import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).with_name("Bybit_Trading_Engine_v14_research.py")
spec = importlib.util.spec_from_file_location("research_engine_gap", ENGINE_PATH)
engine_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine_mod
spec.loader.exec_module(engine_mod)


def make_engine(max_chase_pct=1.5):
    e = engine_mod.UnifiedQuantEngine.__new__(engine_mod.UnifiedQuantEngine)
    e.cfg = engine_mod.BotConfig(timeframe="15m", max_chase_limit_pct=max_chase_pct)
    e.open_positions = {}
    e.pending = {}
    e.trade_seq = 0
    e._persist = lambda: None

    class RiskSpy:
        current_equity = 10_000.0
        kill_switch_triggered = False

        @staticmethod
        def can_open_new_trade(count):
            return True, "OK"

        @staticmethod
        def calculate_position_size(entry_price, stop_price, order_type="market", risk_budget_usdt=None):
            return 1000.0, min(10.0, risk_budget_usdt) if risk_budget_usdt is not None else 10.0

    e.risk_mgr = RiskSpy()
    return e


def pending_signal(order_type="market", ref=100.0):
    return {
        "direction": "long", "entry_price": ref, "order_type": order_type,
        "strategy": "test", "stop_dist": 2.0,
    }


def candle(open_, high, low, close, ts=1_800_000_000_000):
    return engine_mod.Candle(ts=ts, open=open_, high=high, low=low, close=close, volume=10)


def test_market_long_gap_above_chase_limit_is_cancelled():
    e = make_engine(max_chase_pct=1.5)
    e.pending["BTCUSDT"] = pending_signal("market", 100.0)
    opened = e._try_fill_pending("BTCUSDT", candle(103.0, 104.0, 102.5, 103.5))
    assert opened is False
    assert "BTCUSDT" not in e.open_positions
    assert "BTCUSDT" not in e.pending


def test_market_long_gap_within_limit_fills_at_next_open():
    e = make_engine(max_chase_pct=1.5)
    e.pending["BTCUSDT"] = pending_signal("market", 100.0)
    opened = e._try_fill_pending("BTCUSDT", candle(101.0, 102.0, 100.5, 101.5))
    assert opened is True
    pos = e.open_positions["BTCUSDT"]
    assert pos.entry_price == 101.0
    assert pos.stop_price == 99.0


def test_limit_buy_gapped_below_limit_fills_at_open_not_worse_limit():
    e = make_engine(max_chase_pct=1.5)
    e.pending["BTCUSDT"] = pending_signal("limit", 100.0)
    opened = e._try_fill_pending("BTCUSDT", candle(98.0, 99.0, 97.0, 98.5))
    assert opened is True
    assert e.open_positions["BTCUSDT"].entry_price == 98.0


def test_limit_buy_not_touched_is_not_filled():
    e = make_engine(max_chase_pct=1.5)
    e.pending["BTCUSDT"] = pending_signal("limit", 100.0)
    opened = e._try_fill_pending("BTCUSDT", candle(101.0, 102.0, 100.2, 101.5))
    assert opened is False
    assert "BTCUSDT" not in e.open_positions
    assert "BTCUSDT" not in e.pending


def make_position(direction, entry=100.0, stop=95.0):
    return engine_mod.OpenPositionState(
        trade_id="gap-stop-test",
        symbol="BTCUSDT",
        direction=direction,
        strategy="test",
        entry_ts=1_799_999_100_000,
        entry_price=entry,
        stop_price=stop,
        tp1_price=entry + 10.0 if direction == "long" else entry - 10.0,
        tp2_price=entry + 20.0 if direction == "long" else entry - 20.0,
        initial_stop_dist=abs(entry - stop),
        size_usdt=1000.0,
        risk_usdt=50.0,
        order_type="market",
    )


def test_long_stop_gap_fills_at_open_below_stop():
    e = make_engine()
    pos = make_position("long", entry=100.0, stop=95.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100.0, 101.0, 99.0, 100.0, ts=1_799_998_200_000),
        candle(100.0, 101.0, 99.0, 100.0, ts=1_799_999_100_000),
        candle(90.0, 93.0, 88.0, 91.0),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1] == 90.0, captured[0][1]
    assert captured[0][2] == "stop_loss", captured[0][2]


def test_short_stop_gap_fills_at_open_above_stop():
    e = make_engine()
    pos = make_position("short", entry=100.0, stop=105.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100.0, 101.0, 99.0, 100.0, ts=1_799_998_200_000),
        candle(100.0, 101.0, 99.0, 100.0, ts=1_799_999_100_000),
        candle(110.0, 112.0, 108.0, 109.0),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1] == 110.0, captured[0][1]
    assert captured[0][2] == "stop_loss", captured[0][2]


def test_long_stop_without_gap_fills_at_stop_price():
    e = make_engine()
    pos = make_position("long", entry=100.0, stop=95.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100.0, 101.0, 99.0, 100.0, ts=1_799_998_200_000),
        candle(100.0, 101.0, 99.0, 100.0, ts=1_799_999_100_000),
        candle(98.0, 99.0, 94.0, 96.0),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1] == 95.0, captured[0][1]
    assert captured[0][2] == "stop_loss", captured[0][2]


def test_long_stop_wins_when_same_candle_hits_tp1():
    e = make_engine()
    pos = make_position("long", entry=100.0, stop=95.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100, 101, 99, 100, ts=1_799_998_200_000),
        candle(100, 101, 99, 100, ts=1_799_999_100_000),
        candle(100, 112, 94, 101),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1:3] == (95.0, "stop_loss")
    assert pos.tp1_hit is False
    assert pos.remaining_fraction == 1.0


def test_long_stop_wins_when_same_candle_hits_tp2():
    e = make_engine()
    pos = make_position("long", entry=100.0, stop=95.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100, 101, 99, 100, ts=1_799_998_200_000),
        candle(100, 101, 99, 100, ts=1_799_999_100_000),
        candle(100, 125, 94, 101),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1:3] == (95.0, "stop_loss")
    assert pos.tp1_hit is False
    assert pos.remaining_fraction == 1.0


def test_short_stop_wins_when_same_candle_hits_tp1():
    e = make_engine()
    pos = make_position("short", entry=100.0, stop=105.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100, 101, 99, 100, ts=1_799_998_200_000),
        candle(100, 101, 99, 100, ts=1_799_999_100_000),
        candle(100, 106, 88, 99),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1:3] == (105.0, "stop_loss")
    assert pos.tp1_hit is False
    assert pos.remaining_fraction == 1.0


def test_short_stop_wins_when_same_candle_hits_tp2():
    e = make_engine()
    pos = make_position("short", entry=100.0, stop=105.0)
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = [
        candle(100, 101, 99, 100, ts=1_799_998_200_000),
        candle(100, 101, 99, 100, ts=1_799_999_100_000),
        candle(100, 106, 75, 99),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", history, False, history[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1:3] == (105.0, "stop_loss")
    assert pos.tp1_hit is False
    assert pos.remaining_fraction == 1.0


def test_partial_tp1_then_stop_closes_only_remaining_fraction():
    e = make_engine()
    pos = make_position("long", entry=100.0, stop=95.0)
    pos.tp1_price = 110.0
    pos.tp2_price = 120.0
    e.open_positions["BTCUSDT"] = pos
    # First candle reaches TP1 but not the original stop.
    first = [
        candle(100, 101, 99, 100, ts=1_799_998_200_000),
        candle(100, 101, 99, 100, ts=1_799_999_100_000),
        candle(100, 111, 98, 110),
    ]
    e._close_position = lambda *args: None
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", first, False, first[-1].ts + 900_000)
    assert pos.tp1_hit is True
    assert pos.remaining_fraction == 0.5
    assert pos.realized_tp1_gross_usdt == 50.0

    # A later candle crosses the moved trailing stop; close should account for only the remainder.
    captured = []
    e._close_position = lambda *args: captured.append(args)
    second = [
        first[0], first[1],
        candle(100, 111, 98, 110),
        candle(110, 112, 99, 101),
    ]
    engine_mod.UnifiedQuantEngine._manage_position(e, "BTCUSDT", second, False, second[-1].ts + 900_000)
    assert len(captured) == 1
    assert captured[0][1] == pos.stop_price
    assert captured[0][2] == "trailing_stop"
    assert pos.remaining_fraction == 0.5
    assert pos.realized_tp1_gross_usdt == 50.0



if __name__ == "__main__":
    tests = [
        test_market_long_gap_above_chase_limit_is_cancelled,
        test_market_long_gap_within_limit_fills_at_next_open,
        test_limit_buy_gapped_below_limit_fills_at_open_not_worse_limit,
        test_limit_buy_not_touched_is_not_filled,
        test_long_stop_gap_fills_at_open_below_stop,
        test_short_stop_gap_fills_at_open_above_stop,
        test_long_stop_without_gap_fills_at_stop_price,
        test_long_stop_wins_when_same_candle_hits_tp1,
        test_long_stop_wins_when_same_candle_hits_tp2,
        test_short_stop_wins_when_same_candle_hits_tp1,
        test_short_stop_wins_when_same_candle_hits_tp2,
        test_partial_tp1_then_stop_closes_only_remaining_fraction,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"{len(tests)}/{len(tests)} tests passed")