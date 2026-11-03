"""Deterministic tests for the preregistered H-A relative-strength features."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
engine_spec = importlib.util.spec_from_file_location(
    "relative_strength_engine_integration", ROOT / "Bybit_Trading_Engine_v14_research.py",
)
engine_mod = importlib.util.module_from_spec(engine_spec)
sys.modules[engine_spec.name] = engine_mod
engine_spec.loader.exec_module(engine_mod)
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




def test_strength_score_uses_exact_24h_and_72h_close_indices():
    symbol = "A"
    rows = []
    start = 1_800_000_000_000
    for index in range(73):
        # Flat prior history makes ATR stable; the last close gives known returns.
        close = 100.0 if index < 72 else 110.0
        rows.append(candle(
            start + index * module.H1_MS, close=close,
            open_=close, high=close + 1.0, low=close - 1.0,
        ))
    symbols = ["A", "B", "C", "D", "E"]
    histories = {name: rows if name == symbol else history(name) for name in symbols}
    as_of = rows[-1].ts + module.H1_MS
    context = module.build_strength_context(as_of, histories)
    atr = module._atr_from_completed_bars(rows[:-1])
    expected = (0.5 * (110.0 / 100.0 - 1.0) + 0.5 * (110.0 / 100.0 - 1.0)) / (atr / 110.0)
    assert abs(context["scores"][symbol] - expected) < 1e-12


def test_current_signal_candle_range_does_not_change_strength_atr_denominator():
    symbols = ["A", "B", "C", "D", "E"]
    normal = {name: history(name) for name in symbols}
    expanded = {name: list(rows) for name, rows in normal.items()}
    original = expanded["A"][-1]
    expanded["A"][-1] = candle(
        original.ts, close=original.close, open_=original.open,
        high=original.close * 3.0, low=original.close * 0.1,
    )
    as_of = normal["A"][-1].ts + module.H1_MS
    base_context = module.build_strength_context(as_of, normal)
    expanded_context = module.build_strength_context(as_of, expanded)
    assert base_context["scores"]["A"] == expanded_context["scores"]["A"]
    assert base_context["ranks"]["A"] == expanded_context["ranks"]["A"]


def test_midranks_are_monotonic_and_average_ties():
    ranks = module._midranks({
        "low": -2.0, "tie_a": 0.0, "tie_b": 0.0,
        "high": 2.0, "top": 3.0,
    })
    assert ranks["low"] == 0.0
    assert ranks["tie_a"] == ranks["tie_b"] == 0.375
    assert ranks["high"] == 0.75
    assert ranks["top"] == 1.0




def test_h_a_evaluator_is_wired_into_sparse_shared_capital_replay():
    symbols = ["AUSDT", "BUSDT", "CUSDT", "DUSDT", "EUSDT"]
    start = 1_800_000_000_000
    candles = {}
    for symbol in symbols:
        rows = []
        previous_close = 100.0
        for index in range(90):
            ts = start + index * module.H1_MS
            close = 120.0 if symbol == "AUSDT" and index >= 80 else 100.0
            open_ = previous_close
            rows.append(engine_mod.Candle(
                ts=ts, open=open_, high=max(open_, close) + 1.0,
                low=min(open_, close) - 1.0, close=close, volume=100.0,
            ))
            previous_close = close
        candles[symbol] = rows

    engine = engine_mod.UnifiedQuantEngine(
        journal_output_path="/tmp/ignored_h_a_sparse_integration.json",
        persist_state=False,
    )
    cfg = engine.cfg
    cfg.timeframe = "1h"
    cfg.active_trading_pool = list(symbols)
    cfg.disabled_instruments = []
    cfg.max_concurrent_positions = 5
    cfg.max_risk_trade_pct = 0.5
    cfg.max_portfolio_risk_pct = 2.0
    cfg.max_chase_limit_pct = 100.0
    cfg.stop_atr_mult = 2.5
    cfg.tp1_r_multiple = 2.0
    cfg.tp2_r_multiple = 5.0
    cfg.validate()
    engine.risk_mgr.cfg = cfg
    engine.tg.send_message = lambda *_args, **_kwargs: None

    emitted = []
    def evaluator(symbol, history, config, context):
        signal = module.evaluate_relative_strength_breakout(
            symbol, history, config, context,
        )
        if signal is not None:
            emitted.append((
                symbol, signal["direction"], signal["relative_strength_rank"],
                signal["cross_section_size"], signal["signal_ts"],
            ))
        return None  # inspect signal generation without creating a position

    engine_mod.run_simulation_pass(
        engine, candles, symbols, data_label="H_A_SYNTHETIC_INTEGRATION",
        allow_sparse_data=True,
        signal_evaluator=evaluator,
        signal_context_provider=module.build_strength_context,
    )
    assert emitted == [("AUSDT", "long", 1.0, 5, start + 80 * module.H1_MS)]


if __name__ == "__main__":
    tests = [(name, value) for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for name, test in tests:
        test()
        print("PASS", name)
    print(f"{len(tests)}/{len(tests)} tests passed")
