"""Pure, synthetic-testable H-B v0.1 signal predicate.

This module intentionally does not integrate with the trading engine. It validates
only the causal H1 signal contract; execution, sizing, persistence, exits, PnL and
exchange behavior remain out of scope.
"""
from __future__ import annotations

import math
from dataclasses import asdict
from collections.abc import Mapping, Sequence
from typing import Any

from market_regime import RegimeConfig, classify_candles

H1_INTERVAL_MS = 3_600_000
H_B_POLICY_VERSION = "v0.1"
H_B_STRATEGY = "H-B-mean-reversion"


def _positive_finite(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite positive number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a finite positive number") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{field} must be a finite positive number")
    return result


def evaluate_h_b_signal(
    candles: Sequence[Mapping[str, object]],
    regimes: Sequence[str],
    atr_values: Sequence[object],
    shock_index: int,
) -> dict[str, Any] | None:
    """Evaluate one proposed shock index using data available through t+1 only.

    Contract:
      * regime[t-1] must already be "range";
      * close[t] <= close[t-24] - 2 * ATR[t-1];
      * close[t+1] > high[t];
      * entry is scheduled for the next H1 open (t+2), never at close[t+1].

    Returns None when a validly shaped input does not satisfy the signal. Invalid
    data raises ValueError (fail closed). The function does not inspect candles
    after t+1, does not choose RegimeConfig thresholds, and does not simulate a
    fill or position lifecycle.
    """
    if isinstance(shock_index, bool) or not isinstance(shock_index, int):
        raise ValueError("shock_index must be an integer")
    if len(candles) != len(regimes) or len(candles) != len(atr_values):
        raise ValueError("candles, regimes and atr_values must have equal lengths")
    if shock_index < 24 or shock_index + 1 >= len(candles):
        return None

    start = shock_index - 24
    end = shock_index + 1
    used_rows = candles[start : end + 1]
    parsed: list[dict[str, float | int]] = []
    previous_ts: int | None = None

    for offset, row in enumerate(used_rows):
        absolute_index = start + offset
        raw_ts = row.get("ts")
        if isinstance(raw_ts, bool) or not isinstance(raw_ts, int) or raw_ts <= 0:
            raise ValueError(f"candle[{absolute_index}].ts must be a positive integer")
        ts = raw_ts
        if previous_ts is not None and ts - previous_ts != H1_INTERVAL_MS:
            raise ValueError("H-B requires an uninterrupted exact H1 timestamp grid")
        op = _positive_finite(row.get("open"), f"candle[{absolute_index}].open")
        high = _positive_finite(row.get("high"), f"candle[{absolute_index}].high")
        low = _positive_finite(row.get("low"), f"candle[{absolute_index}].low")
        close = _positive_finite(row.get("close"), f"candle[{absolute_index}].close")
        if high < max(op, low, close) or low > min(op, high, close):
            raise ValueError(f"candle[{absolute_index}] has invalid OHLC boundaries")
        parsed.append({"ts": ts, "open": op, "high": high, "low": low, "close": close})
        previous_ts = ts

    atr_previous = _positive_finite(atr_values[shock_index - 1], "ATR[t-1]")
    if regimes[shock_index - 1] != "range":
        return None

    pre_shock_closes = [
        float(candles[index]["close"])
        for index in range(shock_index - 24, shock_index)
    ]
    shock = parsed[24]
    stabilization = parsed[25]
    shock_threshold = pre_shock_closes[0] - 2.0 * atr_previous
    if float(shock["close"]) > shock_threshold:
        return None
    if float(stabilization["close"]) <= float(shock["high"]):
        return None

    stop_price = float(shock["low"])
    target_price = sum(pre_shock_closes) / 24.0
    if stop_price >= target_price:
        return None

    signal_ts_ms = int(stabilization["ts"])
    return {
        "strategy": H_B_STRATEGY,
        "direction": "long",
        "policy_version": H_B_POLICY_VERSION,
        "shock_index": shock_index,
        "shock_ts_ms": int(shock["ts"]),
        "signal_ts_ms": signal_ts_ms,
        "entry_ts_ms": signal_ts_ms + H1_INTERVAL_MS,
        "stop_price": stop_price,
        "target_price": target_price,
    }



def evaluate_h_b_signal_with_classifier(
    candles: Sequence[Mapping[str, object]],
    config: RegimeConfig,
    shock_index: int,
) -> dict[str, Any] | None:
    """Run the H-B predicate using an explicitly supplied causal regime config.

    Only the prefix through the stabilization close (t+1) is passed to the
    classifier. This prevents later rows from becoming an accidental input to
    the adapter and makes the exact classifier configuration part of signal
    provenance. No default RegimeConfig is silently selected.
    """
    if not isinstance(config, RegimeConfig):
        raise ValueError("H-B requires an explicit RegimeConfig")
    config.validate()
    if isinstance(shock_index, bool) or not isinstance(shock_index, int):
        raise ValueError("shock_index must be an integer")
    if shock_index < 24 or shock_index + 1 >= len(candles):
        return None

    prefix = list(candles[: shock_index + 2])
    classified = classify_candles(prefix, config)
    regimes = [str(row["regime"]) for row in classified]
    atr_values = [row["atr"] if row["atr"] != "" else None for row in classified]
    signal = evaluate_h_b_signal(prefix, regimes, atr_values, shock_index)
    if signal is None:
        return None
    signal["regime_config"] = asdict(config)
    return signal



def prepare_h_b_entry(
    signal: Mapping[str, object] | None,
    entry_candle: Mapping[str, object] | None,
    position_open: bool = False,
) -> dict[str, Any] | None:
    """Validate the scheduled next-open entry without simulating an engine fill.

    The supplied candle must be exactly t+2. Missing bars, timestamp gaps,
    occupied positions, and invalid entry/stop/target geometry fail closed.
    The returned entry_price is the observed candle open, not a promise of an
    executable fill after spread, slippage, queueing, or fees.
    """
    if not isinstance(position_open, bool):
        raise ValueError("position_open must be boolean")
    if position_open or signal is None or entry_candle is None:
        return None
    if not isinstance(signal, Mapping) or not isinstance(entry_candle, Mapping):
        raise ValueError("signal and entry_candle must be mappings")
    if signal.get("strategy") != H_B_STRATEGY or signal.get("direction") != "long":
        raise ValueError("entry signal must be an H-B long signal")
    if signal.get("policy_version") != H_B_POLICY_VERSION:
        raise ValueError("unsupported H-B signal policy version")

    signal_ts = signal.get("signal_ts_ms")
    expected_ts = signal.get("entry_ts_ms")
    if isinstance(signal_ts, bool) or not isinstance(signal_ts, int) or signal_ts <= 0:
        raise ValueError("signal signal_ts_ms must be a positive integer")
    if isinstance(expected_ts, bool) or not isinstance(expected_ts, int) or expected_ts <= 0:
        raise ValueError("signal entry_ts_ms must be a positive integer")
    if expected_ts != signal_ts + H1_INTERVAL_MS:
        raise ValueError("entry timestamp must be exactly one H1 bar after signal")
    raw_ts = entry_candle.get("ts")
    if isinstance(raw_ts, bool) or not isinstance(raw_ts, int) or raw_ts != expected_ts:
        return None

    entry_price = _positive_finite(entry_candle.get("open"), "entry open")
    stop_price = _positive_finite(signal.get("stop_price"), "signal stop_price")
    target_price = _positive_finite(signal.get("target_price"), "signal target_price")
    if entry_price <= stop_price or target_price <= entry_price:
        return None

    prepared = {
        "strategy": signal.get("strategy"),
        "direction": signal.get("direction"),
        "policy_version": signal.get("policy_version"),
        "signal_ts_ms": signal.get("signal_ts_ms"),
        "entry_ts_ms": expected_ts,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": target_price,
    }
    if "regime_config" in signal:
        prepared["regime_config"] = signal["regime_config"]
    return prepared
