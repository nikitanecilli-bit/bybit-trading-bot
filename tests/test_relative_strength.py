"""Deterministic tests for the preregistered H-A relative-strength features."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "relative_strength_breakout_test", ROOT / "relative_strength_breakout.py",
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def candle(ts, close=100.0, open_=100.0, high=101.0, low=99.0):
    return SimpleNamespace(
        ts=ts, open=open_, high=high, low=low, close=close, volume=100.0,
    )


def history(symbol, *, current_close=100.0, current_high=101.0,
            current_low=99.0, current_open=100.0, drift=0.0, offset=0):
    rows = []
    start = 1_800_000_000_000 + offset * module.H1_MS
    for index in range(72):
        close = 100.0 * (1.0 + drift) ** index
        rows.append(candle(start + index * module.H1_MS, close=close,
                           open_=close, high=close + 1.0, low=close - 1.0))
    rows.append(candle(
        start + 72 * module.H1_MS, close=current_close,
        open_=current_open, high=current_high, low=current_low,
    ))
    return rows


def config(symbols):
    return SimpleNamespace(
        timeframe="1h", active_trading_pool=list(symbols), disabled_instruments=set(),
        blocked_sessions_utc=set(), blocked_weekdays_utc=set(),
        blocked_signal_hours_utc=set(), blocked_directions=set(),
        max_chase_limit_pct=100.0, stop_atr_mult=2.0,
        tp1_r_multiple=1.0, tp2_r_multiple=2.0,
    )


def test_midrank_gives_identical_symbols_neutral_rank():
    symbols = ["A", "B", "C", "D", "E"]
    rows = {symbol: history(symbol) for symbol in symbols}
    as_of = rows["A"][-1].ts + module.H1_MS
    context = module.build_strength_context(as_of, rows)
    assert context["cross_section_size"] == 5
    assert context["eligible_symbols"] == tuple(symbols)
    assert context["ranks"] == {symbol: 0.5 for symbol in symbols}


def test_cross_section_requires_five_symbols_with_full_72h_history():
    symbols = ["A", "B", "C", "D", "E"]
    rows = {symbol: history(symbol) for symbol in symbols[:4]}
    short = rows["A"][-72:]
    rows["E"] = short
    as_of = rows["A"][-1].ts + module.H1_MS
    context = module.build_strength_context(as_of, rows)
    assert context["cross_section_size"] == 4
    assert context["eligible_symbols"] == ("A", "B", "C", "D")
    assert context["ranks"] == {}


def test_context_rejects_history_from_a_different_timestamp():
    rows = {symbol: history(symbol) for symbol in ["A", "B", "C", "D", "E"]}
    as_of = rows["A"][-1].ts + module.H1_MS
    rows["E"] = history("E", offset=1)
    try:
        module.build_strength_context(as_of, rows)
    except ValueError as exc:
        assert "not aligned" in str(exc)
    else:
        raise AssertionError("future/misaligned history must fail closed")


def test_top_ranked_donchian_breakout_generates_long_signal():
    symbols = ["A", "B", "C", "D", "E"]
    rows = {symbol: history(symbol) for symbol in symbols[:-1]}
    rows["E"] = history(
        "E", current_close=120.0, current_open=100.0,
        current_high=120.5, current_low=99.5,
    )
    as_of = rows["A"][-1].ts + module.H1_MS
    context = module.build_strength_context(as_of, rows)
    signal = module.evaluate_relative_strength_breakout("E", rows["E"], config(symbols), context)
    assert context["ranks"]["E"] == 1.0
    assert signal is not None
    assert signal["direction"] == "long"
    assert signal["order_type"] == "market"
    assert signal["strategy"] == "H-A-relative-strength-breakout"


def test_bottom_ranked_donchian_breakout_generates_short_signal():
    symbols = ["A", "B", "C", "D", "E"]
    rows = {symbol: history(symbol) for symbol in symbols[1:]}
    rows["A"] = history(
        "A", current_close=80.0, current_open=100.0,
        current_high=100.5, current_low=79.5,
    )
    as_of = rows["B"][-1].ts + module.H1_MS
    context = module.build_strength_context(as_of, rows)
    signal = module.evaluate_relative_strength_breakout("A", rows["A"], config(symbols), context)
    assert context["ranks"]["A"] == 0.0
    assert signal is not None
    assert signal["direction"] == "short"


def test_signal_rejects_context_from_future_or_other_bar():
    symbols = ["A", "B", "C", "D", "E"]
    rows = {symbol: history(symbol) for symbol in symbols}
    as_of = rows["A"][-1].ts + module.H1_MS
    context = module.build_strength_context(as_of, rows)
    context["as_of_ts"] += module.H1_MS
    try:
        module.evaluate_relative_strength_breakout("A", rows["A"], config(symbols), context)
    except ValueError as exc:
        assert "timestamp" in str(exc)
    else:
        raise AssertionError("mismatched context timestamp must fail closed")


if __name__ == "__main__":
    tests = [(name, value) for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for name, test in tests:
        test()
        print("PASS", name)
    print(f"{len(tests)}/{len(tests)} tests passed")
