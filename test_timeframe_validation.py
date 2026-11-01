"""Regression tests: CSV candle spacing must match the configured engine timeframe."""
import importlib.util
import sys
from pathlib import Path

ENGINE_PATH = Path(__file__).with_name("Bybit_Trading_Engine_v14_research.py")
spec = importlib.util.spec_from_file_location("research_engine_timeframe", ENGINE_PATH)
engine_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine_mod
spec.loader.exec_module(engine_mod)


def candles(step_ms, count=3):
    return [
        engine_mod.Candle(
            ts=1_800_000_000_000 + i * step_ms,
            open=100.0, high=101.0, low=99.0, close=100.5, volume=10.0,
        )
        for i in range(count)
    ]


def test_matching_h1_interval_is_accepted():
    engine_mod.validate_candle_timeframe({"BTCUSDT": candles(3_600_000)}, "1h")


def test_mismatched_15m_csv_with_h1_config_is_rejected():
    try:
        engine_mod.validate_candle_timeframe({"BTCUSDT": candles(900_000)}, "1h")
    except ValueError as exc:
        assert "не соответствует cfg.timeframe='1h'" in str(exc), exc
    else:
        raise AssertionError("15m candles must not be accepted with an H1 config")


def test_mixed_interval_data_is_rejected():
    rows = candles(3_600_000)
    rows[2] = engine_mod.Candle(
        ts=rows[1].ts + 900_000, open=100, high=101, low=99, close=100, volume=10
    )
    try:
        engine_mod.validate_candle_timeframe({"ETHUSDT": rows}, "1h")
    except ValueError as exc:
        assert "не соответствует cfg.timeframe='1h'" in str(exc), exc
    else:
        raise AssertionError("mixed intervals must be rejected")


def test_unsupported_timeframe_is_rejected():
    try:
        engine_mod.validate_candle_timeframe({"BTCUSDT": candles(3_600_000)}, "7m")
    except ValueError as exc:
        assert "Неподдерживаемый timeframe" in str(exc), exc
    else:
        raise AssertionError("unsupported timeframe must be rejected")


def test_empty_data_is_rejected():
    try:
        engine_mod.validate_candle_timeframe({}, "1h")
    except ValueError as exc:
        assert "Нет свечных данных" in str(exc), exc
    else:
        raise AssertionError("empty data must be rejected")
