#!/usr/bin/env python3
"""Read-only signal-candle attribution for a frozen H-A replay artifact.

No PnL is recomputed and no strategy parameters are changed. Features are
reconstructed from the signal H1 candle (one bar before the next-bar entry)
and bars that were already closed at that signal timestamp.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))

import Bybit_Trading_Engine_v14_research as em
from scripts.cryptofetch_sparse_loader import H1_MS, load_cryptofetch_h1_sparse


NUMERIC_FEATURES = (
    "signal_range_atr",
    "signal_body_atr",
    "signal_body_fraction",
    "signal_directional_body_atr",
    "signal_directional_close_location",
    "signal_upper_wick_fraction",
    "signal_lower_wick_fraction",
    "signal_wick_against_trade_fraction",
    "signal_wick_with_trade_fraction",
    "signal_volume_ratio_20",
    "signal_volume_vs_prebreak6",
    "signal_range_vs_prebreak_tr6",
    "signal_gap_in_direction_atr",
    "breakout_close_clearance_atr",
    "breakout_wick_overshoot_atr",
    "prior_close_distance_to_boundary_atr",
    "prior_donchian_width_atr",
    "prebreak_range6_atr",
    "prebreak_range6_to_20",
    "prebreak_tr_mean6_atr",
    "prebreak_volume6_vs20",
    "entry_adverse_gap_atr",
    "initial_stop_distance_atr",
    "post_entry_completed_bars",
    "post_entry_1bar_close_return_r",
    "post_entry_3bar_close_return_r",
    "post_entry_6bar_close_return_r",
    "post_entry_1bar_close_return_atr",
    "post_entry_3bar_close_return_atr",
    "post_entry_6bar_close_return_atr",
    "post_entry_first3_max_favorable_r",
    "post_entry_first3_max_adverse_r",
    "post_entry_first3_mean_true_range_atr",
    "post_entry_first3_mean_volume_vs_signal",
    "post_entry_retest_inside_1bar",
    "post_entry_retest_inside_3bars",
    "post_entry_retest_inside_6bars",
)


def _parse_utc_ms(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("trade timestamp must include timezone")
    return int(parsed.astimezone(timezone.utc).timestamp() * 1000)


def _safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0 or not math.isfinite(denominator):
        return None
    value = numerator / denominator
    return value if math.isfinite(value) else None


def _true_ranges(rows: list[Any]) -> list[float]:
    result = []
    for index in range(1, len(rows)):
        current, previous = rows[index], rows[index - 1]
        result.append(max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        ))
    return result


def extract_signal_features(
    rows: list[Any],
    index_by_ts: dict[int, int],
    trade: dict[str, Any],
) -> dict[str, Any]:
    """Reconstruct only information available at signal close, before next-bar fill."""
    entry_ts = _parse_utc_ms(str(trade["entry_date"]))
    entry_index = index_by_ts.get(entry_ts)
    if entry_index is None:
        raise ValueError(f"{trade.get('symbol')}: entry candle is absent from source history")
    signal_index = entry_index - 1
    if signal_index < 20:
        raise ValueError(f"{trade.get('symbol')}: insufficient pre-signal history")

    signal = rows[signal_index]
    previous = rows[:signal_index]
    if signal.ts + H1_MS != entry_ts:
        raise ValueError(f"{trade.get('symbol')}: trade is not a strict next-H1-bar entry")
    previous20 = previous[-20:]
    previous6 = previous[-6:]
    if len(previous20) != 20 or len(previous6) != 6:
        raise ValueError(f"{trade.get('symbol')}: insufficient Donchian/compression history")

    direction = str(trade["direction"]).lower()
    if direction not in {"long", "short"}:
        raise ValueError(f"unsupported trade direction: {direction}")
    sign = 1.0 if direction == "long" else -1.0

    atr = em.QuantStrategyCore.compute_atr(previous, 14)
    if atr <= 0 or not math.isfinite(atr):
        raise ValueError(f"{trade.get('symbol')}: invalid pre-signal ATR")

    bar_range = max(0.0, float(signal.high - signal.low))
    body = abs(float(signal.close - signal.open))
    close_location = _safe_div(float(signal.close - signal.low), bar_range)
    if close_location is None:
        close_location = 0.5
    upper_wick = max(0.0, float(signal.high - max(signal.open, signal.close)))
    lower_wick = max(0.0, float(min(signal.open, signal.close) - signal.low))
    upper_wick_fraction = _safe_div(upper_wick, bar_range) or 0.0
    lower_wick_fraction = _safe_div(lower_wick, bar_range) or 0.0

    prior_high = max(float(row.high) for row in previous20)
    prior_low = min(float(row.low) for row in previous20)
    prior_range20 = prior_high - prior_low
    prior_range6 = max(float(row.high) for row in previous6) - min(
        float(row.low) for row in previous6
    )
    tr6 = _true_ranges(previous[-7:])
    mean_tr6 = statistics.fmean(tr6) if tr6 else 0.0
    mean_vol20 = statistics.fmean(float(row.volume) for row in previous20)
    mean_vol6 = statistics.fmean(float(row.volume) for row in previous6)
    mean_vol3 = statistics.fmean(float(row.volume) for row in previous[-3:])

    if direction == "long":
        clearance = (float(signal.close) - prior_high) / atr
        wick_overshoot = (float(signal.high) - prior_high) / atr
        prior_close_distance = (prior_high - float(previous[-1].close)) / atr
        close_aligned = close_location
        wick_against = upper_wick_fraction
        wick_with = lower_wick_fraction
    else:
        clearance = (prior_low - float(signal.close)) / atr
        wick_overshoot = (prior_low - float(signal.low)) / atr
        prior_close_distance = (float(previous[-1].close) - prior_low) / atr
        close_aligned = 1.0 - close_location
        wick_against = lower_wick_fraction
        wick_with = upper_wick_fraction

    entry_price = float(trade["entry_price"])
    adverse_entry_gap = sign * (entry_price - float(signal.close)) / atr
    signal_gap = sign * (float(signal.open) - float(previous[-1].close)) / atr
    range_vs_tr6 = _safe_div(bar_range, mean_tr6)

    features = {
        "signal_ts_ms": int(signal.ts),
        "signal_range_atr": bar_range / atr,
        "signal_body_atr": body / atr,
        "signal_body_fraction": _safe_div(body, bar_range) or 0.0,
        "signal_directional_body_atr": sign * (float(signal.close) - float(signal.open)) / atr,
        "signal_directional_close_location": close_aligned,
        "signal_upper_wick_fraction": upper_wick_fraction,
        "signal_lower_wick_fraction": lower_wick_fraction,
        "signal_wick_against_trade_fraction": wick_against,
        "signal_wick_with_trade_fraction": wick_with,
        "signal_volume_ratio_20": _safe_div(float(signal.volume), mean_vol20),
        "signal_volume_vs_prebreak6": _safe_div(float(signal.volume), mean_vol6),
        "signal_range_vs_prebreak_tr6": range_vs_tr6,
        "signal_gap_in_direction_atr": signal_gap,
        "breakout_close_clearance_atr": clearance,
        "breakout_wick_overshoot_atr": wick_overshoot,
        "prior_close_distance_to_boundary_atr": prior_close_distance,
        "prior_donchian_width_atr": prior_range20 / atr,
        "prebreak_range6_atr": prior_range6 / atr,
        "prebreak_range6_to_20": _safe_div(prior_range6, prior_range20),
        "prebreak_tr_mean6_atr": _safe_div(mean_tr6, atr),
        "prebreak_volume6_vs20": _safe_div(mean_vol6, mean_vol20),
        "entry_adverse_gap_atr": adverse_entry_gap,
    }

    # Post-entry diagnostics are strictly bounded by the trade's exit time.
    # For intrabar exits, the exit candle is excluded because its close occurs
    # after the modeled fill; time-stop/end-of-test exits occur at bar close.
    exit_ts = _parse_utc_ms(str(trade["exit_date"]))
    close_exit = str(trade.get("exit_reason")) in {"time_stop", "end_of_test"}
    completed = []
    for candle in rows[entry_index:]:
        candle_close_ts = candle.ts + H1_MS
        if candle_close_ts > exit_ts:
            break
        if not close_exit and candle_close_ts >= exit_ts:
            continue
        completed.append(candle)

    size_usdt = float(trade.get("size_usdt") or 0.0)
    risk_usdt = float(trade.get("risk_usdt") or 0.0)
    entry_price = float(trade["entry_price"])
    recorded_stop_dist = trade.get("initial_stop_dist")
    stop_dist = (
        float(recorded_stop_dist) if recorded_stop_dist not in (None, 0, 0.0)
        else (risk_usdt * entry_price / size_usdt if size_usdt > 0 else 0.0)
    )
    if stop_dist <= 0 or not math.isfinite(stop_dist):
        raise ValueError(f"{trade.get('symbol')}: invalid initial stop distance")
    features["initial_stop_distance_atr"] = stop_dist / atr
    features["post_entry_completed_bars"] = len(completed)

    for horizon in (1, 3, 6):
        if len(completed) >= horizon:
            close_price = float(completed[horizon - 1].close)
            close_return = sign * (close_price - entry_price)
            features[f"post_entry_{horizon}bar_close_return_r"] = close_return / stop_dist
            features[f"post_entry_{horizon}bar_close_return_atr"] = close_return / atr
            features[f"post_entry_retest_inside_{'1bar' if horizon == 1 else str(horizon) + 'bars'}"] = int(
                any(
                    (float(row.close) <= prior_high) if direction == "long"
                    else (float(row.close) >= prior_low)
                    for row in completed[:horizon]
                )
            )
        else:
            features[f"post_entry_{horizon}bar_close_return_r"] = None
            features[f"post_entry_{horizon}bar_close_return_atr"] = None
            features[f"post_entry_retest_inside_{'1bar' if horizon == 1 else str(horizon) + 'bars'}"] = None

    if len(completed) >= 3:
        first3 = completed[:3]
        if direction == "long":
            favorable = max(float(row.high) - entry_price for row in first3) / stop_dist
            adverse = max(entry_price - float(row.low) for row in first3) / stop_dist
        else:
            favorable = max(entry_price - float(row.low) for row in first3) / stop_dist
            adverse = max(float(row.high) - entry_price for row in first3) / stop_dist
        post_tr = _true_ranges([signal, *first3])
        features["post_entry_first3_max_favorable_r"] = favorable
        features["post_entry_first3_max_adverse_r"] = adverse
        features["post_entry_first3_mean_true_range_atr"] = (
            statistics.fmean(post_tr) / atr if post_tr else None
        )
        features["post_entry_first3_mean_volume_vs_signal"] = (
            statistics.fmean(float(row.volume) for row in first3) / float(signal.volume)
            if float(signal.volume) > 0 else None
        )
    else:
        features["post_entry_first3_max_favorable_r"] = None
        features["post_entry_first3_max_adverse_r"] = None
        features["post_entry_first3_mean_true_range_atr"] = None
        features["post_entry_first3_mean_volume_vs_signal"] = None

    return features


def _summarize_group(rows: list[dict[str, Any]], fold: str, variant: str, reason: str):
    count = len(rows)
    result: dict[str, Any] = {
        "fold": fold,
        "variant": variant,
        "exit_reason": reason,
        "trades": count,
        "net_pnl_total": round(sum(float(row["net_pnl"]) for row in rows), 4),
        "avg_net_pnl": round(statistics.fmean(float(row["net_pnl"]) for row in rows), 4),
        "avg_mfe_r": round(statistics.fmean(float(row["mfe_r"]) for row in rows), 4),
        "avg_mae_r": round(statistics.fmean(float(row["mae_r"]) for row in rows), 4),
        "median_mfe_r": round(statistics.median(float(row["mfe_r"]) for row in rows), 4),
        "median_mae_r": round(statistics.median(float(row["mae_r"]) for row in rows), 4),
    }
    for field in NUMERIC_FEATURES:
        values = [float(row[field]) for row in rows if row.get(field) is not None]
        result[f"n_{field}"] = len(values)
        result[f"avg_{field}"] = round(statistics.fmean(values), 6) if values else None
        result[f"median_{field}"] = round(statistics.median(values), 6) if values else None
    return result


def run_diagnostics(results_dir: Path, archive_dir: Path, output_dir: Path) -> dict[str, Any]:
    results_path = results_dir / "results.json"
    manifest_path = results_dir / "archive_manifest.json"
    if not results_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError("results.json and archive_manifest.json are required")

    results = json.loads(results_path.read_text(encoding="utf-8"))
    archived_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    data, current_manifest, archive_summary = load_cryptofetch_h1_sparse(archive_dir)

    expected = {row["symbol"]: row for row in archived_manifest.get("symbols", [])}
    current = {row["symbol"]: row for row in current_manifest}
    if set(expected) != set(current):
        raise ValueError("source archive symbol manifest differs from replay artifact")
    for symbol in sorted(expected):
        for field in ("archive_sha256", "bars_in_source", "first_ts", "last_ts", "common_end_ts"):
            if expected[symbol].get(field) != current[symbol].get(field):
                raise ValueError(f"{symbol}: archive manifest mismatch in {field}")

    index_by_symbol = {
        symbol: {candle.ts: index for index, candle in enumerate(rows)}
        for symbol, rows in data.items()
    }
    enriched: list[dict[str, Any]] = []
    cohorts: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for fold_result in results.get("results", []):
        fold = str(fold_result["fold"])
        for variant_key in ("baseline", "h_a"):
            variant = str(fold_result[variant_key]["variant"])
            for trade in fold_result[variant_key].get("trades_ledger", []):
                symbol = str(trade["symbol"])
                if symbol not in data:
                    raise ValueError(f"{symbol}: trade symbol absent from audited archive")
                features = extract_signal_features(data[symbol], index_by_symbol[symbol], trade)
                entry_ts = _parse_utc_ms(str(trade["entry_date"]))
                exit_ts = _parse_utc_ms(str(trade["exit_date"]))
                row = {
                    "fold": fold,
                    "variant": variant,
                    "symbol": symbol,
                    "direction": trade["direction"],
                    "session": trade.get("session"),
                    "exit_reason": trade["exit_reason"],
                    "entry_date": trade["entry_date"],
                    "exit_date": trade["exit_date"],
                    "holding_h1_bars": round((exit_ts - entry_ts) / H1_MS, 4),
                    "entry_price": trade["entry_price"],
                    "exit_price": trade["exit_price"],
                    "gross_pnl": trade["gross_pnl"],
                    "fees": trade["fees"],
                    "slippage": trade["slippage"],
                    "net_pnl": trade["net_pnl"],
                    "risk_usdt": trade["risk_usdt"],
                    "risk_pct": trade["risk_pct"],
                    "gross_r_multiple": trade["gross_r_multiple"],
                    "r_multiple": trade["r_multiple"],
                    "mae_r": trade["mae_r"],
                    "mfe_r": trade["mfe_r"],
                    "order_type": trade["order_type"],
                    "initial_stop_dist": trade.get("initial_stop_dist"),
                    "initial_stop_price": trade.get("initial_stop_price"),
                    "tp1_price": trade.get("tp1_price"),
                    "tp2_price": trade.get("tp2_price"),
                    "tp1_hit": trade.get("tp1_hit"),
                    "tp1_ts_ms": trade.get("tp1_ts_ms"),
                    "realized_tp1_gross_usdt": trade.get("realized_tp1_gross_usdt"),
                    "remaining_fraction_at_exit": trade.get("remaining_fraction_at_exit"),
                    "final_stop_price": trade.get("final_stop_price"),
                    **features,
                }
                enriched.append(row)
                cohorts[(fold, variant, str(trade["exit_reason"]))].append(row)
                cohorts[("ALL", variant, str(trade["exit_reason"]))].append(row)

    summary_rows = [
        _summarize_group(rows, fold, variant, reason)
        for (fold, variant, reason), rows in sorted(cohorts.items())
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    trade_fields = list(enriched[0]) if enriched else []
    summary_fields = list(summary_rows[0]) if summary_rows else []
    with (output_dir / "trade_signal_features.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=trade_fields)
        writer.writeheader()
        writer.writerows(enriched)
    with (output_dir / "cohort_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    report = {
        "schema_version": 1,
        "classification": "read_only_descriptive_attribution_not_a_strategy_test",
        "data_source": results.get("data_source"),
        "source_archive_summary": archive_summary,
        "source_archive_manifest_sha256_match": True,
        "source_replay_run_artifact_manifest": "archive_manifest.json",
        "trade_rows": len(enriched),
        "cohort_rows": len(summary_rows),
        "features_use_signal_bar_and_earlier_bars_only": True,
        "signal_bar_is_one_H1_bar_before_entry_bar": True,
        "intrabar_path_order_is_not_inferred": True,
        "outputs": ["trade_signal_features.csv", "cohort_summary.csv"],
    }
    (output_dir / "diagnostic_manifest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--archive-dir", type=Path, default=ROOT / "data" / "archives" / "cryptofetch")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run_diagnostics(args.results_dir, args.archive_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
