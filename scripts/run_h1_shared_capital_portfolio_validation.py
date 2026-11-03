#!/usr/bin/env python3
"""Shared-capital H1 portfolio validation for signal-quality variants.

Uses synchronized Binance OHLCV as a Bybit market-data proxy. Each fold is a
portfolio simulation with one shared 10,000 USDT account, not 10,000 USDT per
symbol. Limit fills require OHLC penetration, but queue position, spread,
partial fills, and adverse selection are not modelled.
"""
from __future__ import annotations
import csv
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import Bybit_Trading_Engine_v14_research as em
from multibar_limit_wait import evaluate_limit_wait, prepare_signal_for_next_bar_fill

FOLDS = [(1, 0.50, 0.65), (2, 0.65, 0.80), (3, 0.80, 1.00)]
VOL_THRESHOLDS = [1.2, 1.6, 2.0, 2.5]
BREAKOUT_ATR_THRESHOLDS = [0.0, 0.10, 0.25]
ENTRY_OFFSET_BPS = 20.0
ENTRY_PENETRATION_BPS = 5.0
WAIT_BARS = 3
STARTING_CAPITAL = 10_000.0
MAX_CONCURRENT_POSITIONS = 5
COST_MULTIPLIERS = [1.0, 1.5, 2.0]
BASE_TAKER_FEE = em.TAKER_FEE
BASE_MAKER_FEE = em.MAKER_FEE
BASE_TAKER_SLIP = em.TAKER_SLIP


def resolve_execution_snapshot_dirs(environ=None):
    """Require archived point-in-time Bybit instrument and risk-tier snapshots."""
    env = os.environ if environ is None else environ
    instrument_dir = Path(env.get(
        "BYBIT_INSTRUMENT_SPECS_DIR", "data/instrument_specs/linear"
    ))
    risk_tier_dir = Path(env.get(
        "BYBIT_RISK_TIERS_DIR", "data/instrument_specs/risk_limits"
    ))
    for label, directory in (
        ("instrument specs", instrument_dir),
        ("risk tiers", risk_tier_dir),
    ):
        if not directory.is_dir():
            raise SystemExit(
                f"Missing Bybit {label} snapshot directory: {directory}. "
                "Refusing legacy notional-proxy market PnL replay."
            )
        if not list(directory.glob("*.json")):
            raise SystemExit(
                f"No dated Bybit {label} snapshots in {directory}. "
                "Refusing legacy notional-proxy market PnL replay."
            )
    return str(instrument_dir), str(risk_tier_dir)


def _snapshot_timestamp_ms(path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = payload.get("fetched_at") if isinstance(payload, dict) else None
        parsed = datetime.fromisoformat(str(fetched_at).replace("Z", "+00:00"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise SystemExit(f"Invalid dated Bybit snapshot metadata in {path}: {exc}") from exc
    if parsed.tzinfo is None:
        raise SystemExit(f"Bybit snapshot timestamp must include timezone: {path}")
    return int(parsed.timestamp() * 1000)


def validate_snapshot_history_coverage(
    instrument_specs_dir, risk_tiers_dir, start_ts, end_ts,
    max_age_ms=30 * 24 * 60 * 60 * 1000,
):
    """Require point-in-time snapshots to cover every tested timestamp within max age."""
    if end_ts < start_ts or max_age_ms < 0:
        raise ValueError("invalid snapshot coverage interval or max_age_ms")
    for label, directory in (
        ("instrument specs", Path(instrument_specs_dir)),
        ("risk tiers", Path(risk_tiers_dir)),
    ):
        files = sorted(directory.glob("*.json"))
        stamps = sorted(_snapshot_timestamp_ms(path) for path in files)
        eligible = [stamp for stamp in stamps if stamp <= start_ts]
        if not eligible:
            raise SystemExit(
                f"No dated Bybit {label} snapshot at or before test start "
                f"({start_ts}); a current snapshot cannot validate historical candles."
            )
        covered_stamps = [eligible[-1]] + [
            stamp for stamp in stamps if eligible[-1] < stamp <= end_ts
        ]
        previous = covered_stamps[0]
        if start_ts - previous > max_age_ms:
            raise SystemExit(
                f"Bybit {label} history starts stale: age_ms={start_ts - previous}, "
                f"max_age_ms={max_age_ms}."
            )
        for stamp in covered_stamps[1:]:
            if stamp - previous > max_age_ms:
                raise SystemExit(
                    f"Gap in Bybit {label} snapshots exceeds max_age_ms: "
                    f"gap_ms={stamp - previous}, max_age_ms={max_age_ms}."
                )
            previous = stamp
        if end_ts - previous > max_age_ms:
            raise SystemExit(
                f"Bybit {label} history ends stale: age_ms={end_ts - previous}, "
                f"max_age_ms={max_age_ms}."
            )


def resolve_funding_dirs(environ=None):
    """Require explicit official Bybit funding and mark-price CSV archives."""
    env = os.environ if environ is None else environ
    funding_dir = Path(env.get("BYBIT_FUNDING_DIR", ""))
    mark_dir = Path(env.get("BYBIT_MARK_PRICE_DIR", ""))
    if not str(env.get("BYBIT_FUNDING_DIR", "")).strip() or not str(env.get("BYBIT_MARK_PRICE_DIR", "")).strip():
        raise SystemExit(
            "BYBIT_FUNDING_DIR and BYBIT_MARK_PRICE_DIR are required; "
            "refusing a PnL replay that silently treats funding as zero."
        )
    for label, directory in (("funding", funding_dir), ("mark-price", mark_dir)):
        if not directory.is_dir() or not list(directory.glob("*.csv")):
            raise SystemExit(
                f"Missing or empty Bybit {label} archive directory: {directory}; "
                "refusing a PnL replay without funding coverage."
            )
    return str(funding_dir), str(mark_dir)


def validate_funding_mark_coverage(
    funding_dir, mark_price_dir, symbols, h1_timestamps, start_ts, end_ts,
    trade_kline_dir,
):
    """Require funding events and Bybit mark candles aligned to every scored H1 bar."""
    from scripts.validate_funding_coverage import validate_coverage

    report = validate_coverage(
        funding_dir, mark_price_dir, symbols, trade_kline_dir=trade_kline_dir
    )
    if not report.get("ok"):
        bad = [row for row in report.get("results", []) if row.get("status") != "ok"]
        raise SystemExit(f"Incomplete Bybit funding/mark coverage: {bad[:10]}")
    expected = {int(ts) for ts in h1_timestamps if start_ts <= int(ts) <= end_ts}
    for symbol in symbols:
        funding_path = Path(funding_dir) / f"{symbol}.csv"
        mark_path = Path(mark_price_dir) / f"{symbol}.csv"
        with funding_path.open("r", encoding="utf-8-sig", newline="") as handle:
            funding_rows = list(csv.DictReader(handle))
        events_in_fold = [
            int(row["funding_timestamp_ms"]) for row in funding_rows
            if start_ts <= int(row["funding_timestamp_ms"]) <= end_ts
        ]
        if not events_in_fold:
            raise SystemExit(
                f"No Bybit funding settlements for {symbol} inside scored fold "
                f"[{start_ts}, {end_ts}]."
            )
        with mark_path.open("r", encoding="utf-8-sig", newline="") as handle:
            mark_rows = list(csv.DictReader(handle))
        mark_ts = {int(row["timestamp_ms"]) for row in mark_rows}
        missing = sorted(expected - mark_ts)
        if missing:
            raise SystemExit(
                f"Bybit mark-price H1 coverage missing {len(missing)} candles for "
                f"{symbol}; first missing timestamps={missing[:5]}."
            )


def resolve_bybit_kline_dir(environ=None):
    """Require official Bybit linear H1 trade-kline CSVs as the signal/execution price source."""
    env = os.environ if environ is None else environ
    raw = str(env.get("BYBIT_KLINE_DIR", "")).strip()
    if not raw:
        raise SystemExit(
            "BYBIT_KLINE_DIR is required; refusing Binance/CryptoFetch proxy candles "
            "for a Bybit execution PnL replay."
        )
    directory = Path(raw)
    if not directory.is_dir() or not list(directory.glob("*.csv")):
        raise SystemExit(
            f"Missing or empty official Bybit H1 kline directory: {directory}."
        )
    return str(directory)


def load_bybit_h1_datasets(directory):
    """Load official Bybit V5 H1 trade candles, rejecting gaps and malformed rows."""
    root = Path(directory)
    required = {"timestamp_ms", "open", "high", "low", "close", "volume", "turnover"}
    raw = {}
    for path in sorted(root.glob("*.csv")):
        symbol = path.stem.upper()
        candles = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise SystemExit(f"{path}: missing Bybit trade-kline columns {sorted(required)}")
            for line_no, row in enumerate(reader, start=2):
                try:
                    ts = int(row["timestamp_ms"])
                    op, hi, low, close, volume, turnover = (
                        float(row[key]) for key in
                        ("open", "high", "low", "close", "volume", "turnover")
                    )
                except (TypeError, ValueError, KeyError, OverflowError) as exc:
                    raise SystemExit(f"{path}:{line_no}: invalid Bybit H1 candle: {exc}") from exc
                values = (op, hi, low, close, volume, turnover)
                if (ts <= 0 or not all(math.isfinite(value) for value in values)
                        or min(op, hi, low, close) <= 0 or volume < 0 or turnover < 0
                        or hi < max(op, low, close) or low > min(op, hi, close)):
                    raise SystemExit(f"{path}:{line_no}: invalid Bybit H1 OHLCV values")
                candles.append(em.Candle(ts, op, hi, low, close, volume))
        candles.sort(key=lambda candle: candle.ts)
        timestamps = [candle.ts for candle in candles]
        if len(timestamps) != len(set(timestamps)):
            raise SystemExit(f"{path}: duplicate Bybit H1 candle timestamps")
        if len(candles) < 500:
            continue
        if any(b - a != 3_600_000 for a, b in zip(timestamps, timestamps[1:])):
            raise SystemExit(f"{path}: missing or irregular H1 candles; refusing partial series")
        raw[symbol] = (str(path), candles)
    return raw


def aligned_h1_datasets(kline_dir):
    allowlist = {
        s.strip().upper() for s in os.getenv("H1_SYMBOL_ALLOWLIST", "").split(",")
        if s.strip()
    }
    raw = load_bybit_h1_datasets(kline_dir)
    if allowlist:
        missing = sorted(allowlist - set(raw))
        if missing:
            raise SystemExit(f"Selected symbols missing Bybit H1 datasets: {missing}")
        raw = {symbol: raw[symbol] for symbol in sorted(allowlist)}
        print("Selected Bybit universe: " + ", ".join(sorted(raw)))
    if len(raw) < 2:
        raise SystemExit(f"Need at least 2 official Bybit H1 symbols, found {len(raw)}")

    ref_symbol, (_, ref_candles) = max(
        raw.items(), key=lambda item: item[1][1][-1].ts - item[1][1][0].ts
    )
    ref_start, ref_end = ref_candles[0].ts, ref_candles[-1].ts
    span = max(1, ref_end - ref_start)
    selected, coverage = {}, {}
    for symbol, item in raw.items():
        candles = item[1]
        start_ts, end_ts = candles[0].ts, candles[-1].ts
        start_lag = max(0.0, (start_ts - ref_start) / span)
        end_lag = max(0.0, (ref_end - end_ts) / span)
        covered = (end_ts - start_ts) / span
        coverage[symbol] = {
            "coverage_pct": round(covered * 100, 1),
            "start_lag_pct": round(start_lag * 100, 1),
            "end_lag_pct": round(end_lag * 100, 1),
        }
        if allowlist or (covered >= 0.70 and start_lag <= 0.15 and end_lag <= 0.15):
            selected[symbol] = item

    if allowlist and len(selected) != len(allowlist):
        raise SystemExit(f"Expected {len(allowlist)} selected symbols, found {len(selected)}")
    elif not allowlist and len(selected) < 10:
        raise SystemExit(
            f"Only {len(selected)} Bybit symbols have >=70% reference-history coverage "
            "with <=15% start/end lag; refusing a misleading short-overlap portfolio."
        )

    common = None
    for _, candles in selected.values():
        timestamps = {candle.ts for candle in candles}
        common = timestamps if common is None else common.intersection(timestamps)
    timestamps = sorted(common or [])
    ref_count = len(ref_candles)
    overlap_pct = len(timestamps) / max(1, ref_count) * 100
    min_bars = 3000 if allowlist else 500
    min_overlap_pct = 30 if allowlist else 65
    if len(timestamps) < min_bars or overlap_pct < min_overlap_pct:
        raise SystemExit(
            f"Insufficient synchronized Bybit H1 overlap: {len(timestamps)} bars "
            f"({overlap_pct:.1f}% of reference; minimum {min_bars} bars and {min_overlap_pct}%)."
        )

    aligned, archives = {}, {}
    for symbol, (path, candles) in selected.items():
        by_ts = {candle.ts: candle for candle in candles}
        aligned[symbol] = [by_ts[ts] for ts in timestamps]
        archives[symbol] = path
    em.check_alignment(aligned)
    print(f"Reference={ref_symbol}; selected {len(aligned)}/{len(raw)} Bybit symbols; "
          f"common overlap={overlap_pct:.1f}% ({len(timestamps)} H1 bars)")
    print("Selected Bybit symbol coverage: " + ", ".join(
        f"{symbol}:{coverage[symbol]['coverage_pct']}%" for symbol in sorted(aligned)
    ))
    return aligned, archives, timestamps

def run_portfolio_variant(base_candles, symbols, timestamps, fold, start_frac, end_frac,
                          min_vol, min_breakout_atr, cost_multiplier,
                          instrument_specs_dir, risk_tiers_dir,
                          funding_dir, mark_price_dir, kline_dir):
    # Explicit cost stress: scale fees and taker slippage from engine defaults.
    em.TAKER_FEE = BASE_TAKER_FEE * cost_multiplier
    em.MAKER_FEE = BASE_MAKER_FEE * cost_multiplier
    em.TAKER_SLIP = BASE_TAKER_SLIP * cost_multiplier
    n = len(timestamps)
    start_idx, end_idx = int(n * start_frac), int(n * end_frac)
    start_ts, end_ts = timestamps[start_idx], timestamps[end_idx - 1]
    # Require as-of exchange metadata throughout the actual scored fold. A
    # present-day snapshot must never be silently applied to older candles.
    validate_snapshot_history_coverage(
        instrument_specs_dir, risk_tiers_dir, start_ts, end_ts
    )
    validate_funding_mark_coverage(
        funding_dir, mark_price_dir, symbols, timestamps, start_ts, end_ts,
        kline_dir,
    )
    # Truncate at fold end, while allowing pre-fold candles for indicator warm-up.
    fold_data = {sym: candles[:end_idx] for sym, candles in base_candles.items()}

    engine = em.UnifiedQuantEngine(
        journal_output_path="/tmp/ignored_h1_portfolio_quality.json",
        instrument_specs_dir=instrument_specs_dir,
        risk_tiers_dir=risk_tiers_dir,
        funding_dir=funding_dir,
        mark_price_dir=mark_price_dir,
    )
    cfg = engine.cfg
    cfg.bot_version = f"h1-portfolio-v{min_vol:g}-b{min_breakout_atr:g}-cost{cost_multiplier:g}"
    cfg.timeframe = "1h"
    cfg.active_trading_pool = list(symbols)
    cfg.capital_usdt = STARTING_CAPITAL
    cfg.max_risk_trade_pct = 1.0
    cfg.max_portfolio_risk_pct = 2.0
    cfg.max_concurrent_positions = MAX_CONCURRENT_POSITIONS
    cfg.daily_stop_loss_pct = 5.0
    cfg.emergency_kill_switch_pct = 30.0
    cfg.donchian_period = 20
    cfg.atr_period = 14
    cfg.min_volume_ratio = min_vol
    cfg.stop_atr_mult = 2.5
    cfg.tp1_r_multiple = 2.0
    cfg.tp2_r_multiple = 5.0
    cfg.atr_trail_mult = 3.0
    cfg.max_hold_bars = 32
    cfg.maker_entry_and_tp1 = True
    cfg.maker_tp1_and_target = False
    cfg.enable_h2_range_fade = False
    cfg.validate()
    engine.risk_mgr.cfg = cfg
    engine.tg.send_message = lambda *_args, **_kwargs: None

    core = em.QuantStrategyCore
    original_eval = core.evaluate_signal

    def wrapped_eval(sym, bars, conf):
        if not bars or not (start_ts <= bars[-1].ts <= end_ts):
            return None
        sig = original_eval(sym, bars, conf)
        if sig is None or str(sig.get("direction", "")).lower() != "long":
            return None
        if float(sig.get("vol_ratio", 0.0)) < min_vol:
            return None
        if min_breakout_atr > 0:
            prev = bars[:-1]
            hi_ch, _, _ = core.compute_donchian_and_volume(prev, conf.donchian_period)
            atr = float(sig.get("atr", 0.0))
            if atr <= 0 or (float(bars[-1].close) - hi_ch) / atr < min_breakout_atr:
                return None
        return sig

    core.evaluate_signal = staticmethod(wrapped_eval)
    original_fill = engine._try_fill_pending
    order_age = {}

    def wrapped_fill(sym, candle):
        if sym not in engine.pending:
            return original_fill(sym, candle)
        sig = engine.pending[sym]
        meta = order_age.get(sym)
        if meta is None:
            sig["entry_price"] = float(sig["entry_price"]) * (1.0 - ENTRY_OFFSET_BPS / 10000.0)
            sig["order_type"] = "limit"
            meta = {"age": 0}
            order_age[sym] = meta
        decision, meta["age"] = evaluate_limit_wait(
            direction=str(sig.get("direction", "long")),
            low=float(candle.low),
            high=float(candle.high),
            limit_price=float(sig["entry_price"]),
            penetration_bps=ENTRY_PENETRATION_BPS,
            age=meta["age"],
            max_wait_bars=WAIT_BARS,
        )
        if decision == "fill":
            # The base engine deliberately accepts only next-bar signals.
            # Adapt only its freshness guard for this research-only delayed fill;
            # retain the original signal timestamp separately for provenance.
            prepare_signal_for_next_bar_fill(
                sig, int(candle.ts), 3_600_000
            )
            filled = original_fill(sym, candle)
            order_age.pop(sym, None)
            return filled
        # Retain the pending order only while its explicit TTL is active.
        if decision == "wait":
            engine.pending.pop(sym, None)
            engine.pending[sym] = sig
            return False
        engine.pending.pop(sym, None)
        getattr(engine, "_bar_entry_risk_budgets", {}).pop(sym, None)
        order_age.pop(sym, None)
        return False

    engine._try_fill_pending = wrapped_fill
    try:
        em.check_alignment(fold_data)
        audit = em.run_simulation_pass(
            engine, fold_data, list(symbols),
            data_label=f"BYBIT_V5 H1 portfolio fold={fold} vol>={min_vol} breakoutATR>={min_breakout_atr}",
        )
    finally:
        core.evaluate_signal = staticmethod(original_eval)

    trades = engine.closed_trades
    funding_costs = sum(t.funding_cost_usdt for t in trades)
    costs = sum(
        t.exchange_fees_usdt + t.slippage_cost_usdt + t.funding_cost_usdt
        for t in trades
    )
    return {
        "timeframe": "1h",
        "fold": fold,
        "variant": f"vol{min_vol:g}_breakATR{min_breakout_atr:g}_cost{cost_multiplier:g}",
        "cost_multiplier": cost_multiplier,
        "min_volume_ratio": min_vol,
        "min_breakout_atr": min_breakout_atr,
        "symbols": len(symbols),
        "shared_starting_capital": STARTING_CAPITAL,
        "max_concurrent_positions": MAX_CONCURRENT_POSITIONS,
        "trades": int(audit["total_trades"]),
        "net_pnl": round(float(audit["net_pnl"]), 2),
        "return_pct": round(float(audit["ret_pct"]), 3),
        "profit_factor": round(float(audit["pf"]), 4),
        "expectancy_r": round(float(audit["expectancy_r"]), 4),
        "max_drawdown_pct": round(float(audit["max_dd_pct"]), 2),
        "costs": round(float(costs), 2),
        "funding_costs": round(float(funding_costs), 2),
        "test_start_ts": start_ts,
        "test_end_ts": end_ts,
    }


def main():
    instrument_specs_dir, risk_tiers_dir = resolve_execution_snapshot_dirs()
    funding_dir, mark_price_dir = resolve_funding_dirs()
    print(f"Strict Bybit execution snapshots: specs={instrument_specs_dir}; risk_tiers={risk_tiers_dir}")
    print(f"Official Bybit costs: funding={funding_dir}; mark_prices={mark_price_dir}")
    kline_dir = resolve_bybit_kline_dir()
    datasets, archives, timestamps = aligned_h1_datasets(kline_dir)
    symbols = sorted(datasets)
    print(f"Aligned H1 portfolio: {len(symbols)} symbols, {len(timestamps)} common bars")
    print(f"Archive sources: {len(set(archives.values()))}; starting capital={STARTING_CAPITAL:.0f} USDT")
    rows = []
    for fold, start_frac, end_frac in FOLDS:
        for min_vol in VOL_THRESHOLDS:
            for min_breakout in BREAKOUT_ATR_THRESHOLDS:
                for cost_multiplier in COST_MULTIPLIERS:
                    result = run_portfolio_variant(
                        datasets, symbols, timestamps, fold, start_frac, end_frac,
                        min_vol, min_breakout, cost_multiplier,
                        instrument_specs_dir, risk_tiers_dir,
                        funding_dir, mark_price_dir, kline_dir,
                    )
                    rows.append(result)
                    print(f"fold={fold} {result['variant']} trades={result['trades']} "
                          f"net={result['net_pnl']:+.2f} ({result['return_pct']:+.2f}%) "
                          f"PF={result['profit_factor']:.3f} DD={result['max_drawdown_pct']:.2f}% "
                          f"costs={result['costs']:.2f}")
    path = "h1_shared_capital_portfolio_validation.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {path}; {len(rows)} portfolio-fold-cost runs. Cost multipliers={COST_MULTIPLIERS}.")
    print("CAVEAT: Binance OHLCV proxy; modelled costs; limit penetration is not a real queue/fill model.")


if __name__ == "__main__":
    main()
