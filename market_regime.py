#!/usr/bin/env python3
"""Causal, rule-based market-regime labels for OHLCV research.

This module is deliberately separate from the trading engine: it labels each
completed candle using only that candle and earlier observations. It does not
change signals, trade execution, or position sizing.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RegimeConfig:
    efficiency_period: int = 20
    atr_period: int = 14
    ema_fast_period: int = 10
    ema_slow_period: int = 30
    slope_lookback: int = 5
    volatility_lookback: int = 100
    trend_er_min: float = 0.35
    range_er_max: float = 0.25
    trend_slope_atr_min: float = 0.25
    range_slope_atr_max: float = 0.15
    high_vol_ratio: float = 1.5
    high_vol_er_max: float = 0.30

    def validate(self) -> None:
        periods = (
            self.efficiency_period, self.atr_period, self.ema_fast_period,
            self.ema_slow_period, self.slope_lookback, self.volatility_lookback,
        )
        if any(isinstance(p, bool) or not isinstance(p, int) or p < 2 for p in periods):
            raise ValueError("all indicator periods must be integers >= 2")
        thresholds = (
            self.trend_er_min, self.range_er_max, self.trend_slope_atr_min,
            self.range_slope_atr_max, self.high_vol_ratio, self.high_vol_er_max,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in thresholds
        ):
            raise ValueError("all regime thresholds must be finite numbers")
        if self.ema_fast_period >= self.ema_slow_period:
            raise ValueError("ema_fast_period must be less than ema_slow_period")
        numeric_thresholds = (
            ("trend_er_min", self.trend_er_min),
            ("range_er_max", self.range_er_max),
            ("trend_slope_atr_min", self.trend_slope_atr_min),
            ("range_slope_atr_max", self.range_slope_atr_max),
            ("high_vol_ratio", self.high_vol_ratio),
            ("high_vol_er_max", self.high_vol_er_max),
        )
        for name, value in numeric_thresholds:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if not 0 <= self.range_er_max < self.trend_er_min <= 1:
            raise ValueError("require 0 <= range_er_max < trend_er_min <= 1")
        if self.trend_slope_atr_min <= 0 or self.range_slope_atr_max < 0:
            raise ValueError("slope thresholds are invalid")
        if self.high_vol_ratio <= 1 or not 0 <= self.high_vol_er_max <= 1:
            raise ValueError("high-volatility thresholds are invalid")


def _finite_positive(value: object, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{field} must be finite and > 0")
    return result


def _ema(values: list[float], period: int) -> list[float]:
    alpha = 2.0 / (period + 1.0)
    out: list[float] = []
    current = values[0]
    for value in values:
        current = alpha * value + (1.0 - alpha) * current
        out.append(current)
    return out


def _rolling_mean(values: list[float], end: int, period: int) -> float | None:
    start = end - period + 1
    if start < 0:
        return None
    window = values[start:end + 1]
    return sum(window) / period


def _efficiency_ratio(closes: list[float], end: int, period: int) -> float | None:
    start = end - period
    if start < 0:
        return None
    net_move = abs(closes[end] - closes[start])
    path = sum(abs(closes[i] - closes[i - 1]) for i in range(start + 1, end + 1))
    if path <= 0:
        return 0.0
    return min(1.0, net_move / path)


def classify_candles(
    candles: Iterable[dict[str, object]],
    config: RegimeConfig | None = None,
) -> list[dict[str, object]]:
    """Return candle rows plus causal features and a regime label.

    Required fields: ts, open, high, low, close. Optional fields are preserved.
    Regime labels are unknown during warm-up; no future candle is consulted.
    """
    cfg = config or RegimeConfig()
    cfg.validate()
    rows = [dict(row) for row in candles]
    if not rows:
        return []
    parsed: list[dict[str, object]] = []
    previous_ts: int | None = None
    previous_close: float | None = None
    for index, row in enumerate(rows, start=1):
        try:
            ts = int(row["ts"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"row {index}: ts must be an integer timestamp") from exc
        if ts <= 0 or (previous_ts is not None and ts <= previous_ts):
            raise ValueError(f"row {index}: timestamps must be positive and strictly increasing")
        op = _finite_positive(row.get("open"), f"row {index} open")
        high = _finite_positive(row.get("high"), f"row {index} high")
        low = _finite_positive(row.get("low"), f"row {index} low")
        close = _finite_positive(row.get("close"), f"row {index} close")
        if high < max(op, low, close) or low > min(op, high, close):
            raise ValueError(f"row {index}: invalid OHLC boundaries")
        tr = high - low if previous_close is None else max(
            high - low, abs(high - previous_close), abs(low - previous_close)
        )
        parsed.append({
            **row, "ts": ts, "open": op, "high": high, "low": low,
            "close": close, "_tr": tr,
        })
        previous_ts, previous_close = ts, close

    closes = [float(row["close"]) for row in parsed]
    trs = [float(row["_tr"]) for row in parsed]
    fast = _ema(closes, cfg.ema_fast_period)
    slow = _ema(closes, cfg.ema_slow_period)
    atr_values: list[float | None] = [
        _rolling_mean(trs, i, cfg.atr_period) for i in range(len(parsed))
    ]
    atr_pct = [
        None if atr is None else atr / closes[i]
        for i, atr in enumerate(atr_values)
    ]

    output: list[dict[str, object]] = []
    warmup = max(
        cfg.efficiency_period + 1,
        cfg.atr_period,
        cfg.ema_slow_period + cfg.slope_lookback,
        cfg.volatility_lookback,
    )
    for i, row in enumerate(parsed):
        atr = atr_values[i]
        er = _efficiency_ratio(closes, i, cfg.efficiency_period)
        slope_atr: float | None = None
        vol_ratio: float | None = None
        if atr is not None and atr > 0 and i >= cfg.slope_lookback:
            slope_atr = (fast[i] - fast[i - cfg.slope_lookback]) / atr
        if atr_pct[i] is not None:
            start = max(0, i - cfg.volatility_lookback + 1)
            history = [x for x in atr_pct[start:i + 1] if x is not None]
            median = statistics.median(history) if history else 0.0
            if median > 0:
                vol_ratio = float(atr_pct[i]) / median

        regime = "unknown"
        direction = "neutral"
        ema_alignment = "unknown"
        if i >= warmup - 1 and er is not None and slope_atr is not None and vol_ratio is not None:
            if fast[i] > slow[i]:
                ema_alignment = "up"
            elif fast[i] < slow[i]:
                ema_alignment = "down"
            else:
                ema_alignment = "neutral"
            if vol_ratio >= cfg.high_vol_ratio and er < cfg.high_vol_er_max:
                regime = "high_vol_chop"
            elif (
                er >= cfg.trend_er_min
                and abs(slope_atr) >= cfg.trend_slope_atr_min
                and ((ema_alignment == "up" and slope_atr > 0)
                     or (ema_alignment == "down" and slope_atr < 0))
            ):
                regime = "trend_up" if ema_alignment == "up" else "trend_down"
                direction = ema_alignment
            elif er <= cfg.range_er_max and abs(slope_atr) <= cfg.range_slope_atr_max:
                regime = "range"
            else:
                regime = "transition"

        clean = {key: value for key, value in row.items() if not key.startswith("_")}
        clean.update({
            "regime": regime,
            "regime_direction": direction,
            "ema_alignment": ema_alignment,
            "efficiency_ratio": "" if er is None else round(er, 8),
            "atr": "" if atr is None else round(atr, 10),
            "atr_pct": "" if atr_pct[i] is None else round(float(atr_pct[i]), 10),
            "ema_slope_atr": "" if slope_atr is None else round(slope_atr, 8),
            "volatility_ratio": "" if vol_ratio is None else round(vol_ratio, 8),
        })
        output.append(clean)
    return output


def read_ohlcv_csv(path: str) -> list[dict[str, object]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"ts", "open", "high", "low", "close"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"input CSV must contain columns: {', '.join(sorted(required))}")
        return [dict(row) for row in reader]


def write_regimes_csv(rows: list[dict[str, object]], path: str) -> None:
    if not rows:
        raise ValueError("refusing to write an empty regime dataset")
    fields = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="OHLCV CSV with ts,open,high,low,close")
    parser.add_argument("--output", required=True, help="Output CSV path")
    args = parser.parse_args()
    labelled = classify_candles(read_ohlcv_csv(args.input))
    write_regimes_csv(labelled, args.output)
    counts: dict[str, int] = {}
    for row in labelled:
        label = str(row["regime"])
        counts[label] = counts.get(label, 0) + 1
    print(f"Wrote {len(labelled)} rows to {args.output}; regimes={counts}")


if __name__ == "__main__":
    main()
