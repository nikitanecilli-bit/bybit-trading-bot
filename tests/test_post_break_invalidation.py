"""Synthetic tests for the disabled-by-default H-C early invalidation exit."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import Bybit_Trading_Engine_v14_research as engine
from test_gap_execution import make_engine, make_position


H1_MS = 3_600_000


def _history(current):
    start = current.ts - 20 * H1_MS
    rows = [
        engine.Candle(start + i * H1_MS, 100.0, 101.0, 99.0, 100.0, 10.0)
        for i in range(20)
    ]
    rows.append(current)
    return rows


def _configured_engine():
    e = make_engine()
    e.cfg.timeframe = "1h"
    e.cfg.enable_post_break_invalidation = True
    e._update_mark_to_market = lambda _ts: None
    e.risk_mgr.on_new_timestamp = lambda _ts: None
    return e


def _position(direction="long", strategy="H1-momentum-breakout"):
    if direction == "long":
        pos = make_position("long", entry=102.0, stop=90.0)
        pos.tp1_price = 130.0
        pos.tp2_price = 140.0
        pos.breakout_level = 101.0
    else:
        pos = make_position("short", entry=98.0, stop=110.0)
        pos.tp1_price = 70.0
        pos.tp2_price = 60.0
        pos.breakout_level = 99.0
    pos.strategy = strategy
    pos.entry_ts = 1_800_000_000_000
    return pos


def _manage(e, pos, curr, fill_bar=True):
    e.open_positions["BTCUSDT"] = pos
    captured = []
    e._close_position = lambda *args: captured.append(args)
    history = _history(curr)
    engine.UnifiedQuantEngine._manage_position(
        e, "BTCUSDT", history, fill_bar, curr.ts + H1_MS,
    )
    return captured


def test_hc_flag_defaults_off_and_is_h1_only():
    assert engine.BotConfig().enable_post_break_invalidation is False

    cfg = engine.BotConfig()
    cfg._apply({
        "strategy": {"timeframe": "1h"},
        "execution_and_exits": {"enable_post_break_invalidation": True},
    })
    cfg.validate()
    assert cfg.enable_post_break_invalidation is True

    invalid = engine.BotConfig()
    invalid._apply({
        "execution_and_exits": {"enable_post_break_invalidation": True},
    })
    try:
        invalid.validate()
    except ValueError as exc:
        assert "только на H1" in str(exc)
    else:
        raise AssertionError("H-C must reject non-H1 timeframes")


def test_hc_long_and_short_retest_close_symmetrically():
    e = _configured_engine()
    long_pos = _position("long")
    long_bar = engine.Candle(long_pos.entry_ts, 102.0, 103.0, 100.0, 100.5, 10.0)
    long_exit = _manage(e, long_pos, long_bar, fill_bar=True)
    assert len(long_exit) == 1
    assert long_exit[0][1] == 100.5
    assert long_exit[0][2] == "breakout_retest_invalidation"

    e = _configured_engine()
    short_pos = _position("short")
    short_bar = engine.Candle(short_pos.entry_ts, 100.0, 100.0, 97.0, 99.5, 10.0)
    short_exit = _manage(e, short_pos, short_bar, fill_bar=True)
    assert len(short_exit) == 1
    assert short_exit[0][1] == 99.5
    assert short_exit[0][2] == "breakout_retest_invalidation"


def test_hc_wick_only_retest_does_not_close():
    e = _configured_engine()
    pos = _position("long")
    bar = engine.Candle(pos.entry_ts, 102.0, 103.0, 100.0, 101.5, 10.0)
    assert _manage(e, pos, bar, fill_bar=True) == []


def test_hc_triggers_on_third_bar_but_not_after_window():
    e = _configured_engine()
    pos = _position("long")
    pos.bars_held = 2
    bar = engine.Candle(pos.entry_ts + 2 * H1_MS, 102.0, 103.0, 100.0, 100.5, 10.0)
    captured = _manage(e, pos, bar, fill_bar=False)
    assert len(captured) == 1
    assert captured[0][2] == "breakout_retest_invalidation"

    e = _configured_engine()
    pos = _position("long")
    pos.bars_held = 3
    bar = engine.Candle(pos.entry_ts + 3 * H1_MS, 102.0, 103.0, 100.0, 100.5, 10.0)
    assert _manage(e, pos, bar, fill_bar=False) == []


def test_hc_does_not_override_stop_or_tp2_priority():
    e = _configured_engine()
    pos = _position("long")
    pos.stop_price = 101.0
    stop_bar = engine.Candle(pos.entry_ts, 102.0, 103.0, 100.0, 100.5, 10.0)
    stopped = _manage(e, pos, stop_bar, fill_bar=False)
    assert len(stopped) == 1
    assert stopped[0][2] == "stop_loss"

    e = _configured_engine()
    pos = _position("long")
    pos.tp2_price = 102.5
    tp_bar = engine.Candle(pos.entry_ts, 102.0, 103.0, 100.5, 100.5, 10.0)
    tp_exit = _manage(e, pos, tp_bar, fill_bar=False)
    assert len(tp_exit) == 1
    assert tp_exit[0][2] == "take_profit"


def test_hc_preserves_tp1_partial_then_closes_remaining_leg():
    e = _configured_engine()
    pos = _position("long")
    pos.tp1_price = 102.5
    pos.tp2_price = 120.0
    bar = engine.Candle(pos.entry_ts, 102.0, 103.0, 100.0, 100.5, 10.0)
    captured = _manage(e, pos, bar, fill_bar=False)
    assert len(captured) == 1
    assert captured[0][2] == "breakout_retest_invalidation"
    assert pos.tp1_hit is True
    assert pos.remaining_fraction == 1.0 - engine.TP1_FRACTION
    assert pos.realized_tp1_gross_usdt > 0


def test_hc_applies_only_to_breakout_strategies_and_does_not_reenter_same_bar():
    e = _configured_engine()
    pos = _position("long", strategy="H2-range-fade")
    bar = engine.Candle(pos.entry_ts, 102.0, 103.0, 100.0, 100.5, 10.0)
    assert _manage(e, pos, bar, fill_bar=True) == []

    # Existing-position processing always returns before signal discovery.
    e = _configured_engine()
    pos = _position("long")
    e.open_positions["BTCUSDT"] = pos
    closed = []

    def close_and_remove(position, *args):
        closed.append(args)
        e.open_positions.pop(position.symbol, None)

    e._close_position = close_and_remove
    e.step_candle("BTCUSDT", _history(bar), evaluate_new_signal=True)
    assert len(closed) == 1
    assert closed[0][0] == bar.close
    assert closed[0][1] == "breakout_retest_invalidation"
    assert "BTCUSDT" not in e.open_positions
    assert e.pending == {}


if __name__ == "__main__":
    tests = [
        test_hc_flag_defaults_off_and_is_h1_only,
        test_hc_long_and_short_retest_close_symmetrically,
        test_hc_wick_only_retest_does_not_close,
        test_hc_triggers_on_third_bar_but_not_after_window,
        test_hc_does_not_override_stop_or_tp2_priority,
        test_hc_preserves_tp1_partial_then_closes_remaining_leg,
        test_hc_applies_only_to_breakout_strategies_and_does_not_reenter_same_bar,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} tests passed")
