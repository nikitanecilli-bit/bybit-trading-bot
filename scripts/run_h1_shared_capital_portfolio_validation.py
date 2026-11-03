#!/usr/bin/env python3
"""Shared-capital H1 portfolio validation for signal-quality variants.

Uses synchronized official Bybit V5 H1 trade OHLCV, funding settlements and
mark-price candles. Each fold is a portfolio simulation with one shared
10,000 USDT account, not 10,000 USDT per symbol. Limit fills require OHLC
penetration, but queue position, spread, partial fills, and adverse selection
are not modelled.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
import os
import platform
import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from contextlib import contextmanager

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
H1_REPLAY_CODE_PATHS = [
    "Bybit_Trading_Engine_v14_research.py",
    "scripts/run_h1_shared_capital_portfolio_validation.py",
    "scripts/select_h1_top5_train_only.py",
    "scripts/snapshot_bybit_linear_universe.py",
    "multibar_limit_wait.py",
    "funding_accounting.py",
    "mark_price_liquidation.py",
    "bybit_risk_tiers.py",
    "bybit_instrument_specs.py",
    "instrument_spec_history.py",
    "exchange_order_sizing.py",
    "market_regime.py",
    "market_structure.py",
    "scripts/validate_funding_coverage.py",
    "funding_archive_manifest.py",
    "bybit_downloader.py",
    "scripts/archive_bybit_market_history.py",
]
SELECTION_INPUT_KEYS = ("kline", "funding", "mark_price", "instrument_specs", "risk_tiers", "universe_snapshot")


def validate_selection_provenance(selection, current_input_files, current_code_files):
    """Reject validation if any selector input or replay dependency changed."""
    recorded_inputs = selection.get("input_files")
    if not isinstance(recorded_inputs, dict):
        raise SystemExit("Selection manifest lacks input file hashes")
    for key in SELECTION_INPUT_KEYS:
        expected_rows = recorded_inputs.get(key)
        actual_rows = current_input_files.get(key)
        if not isinstance(expected_rows, list) or not isinstance(actual_rows, list):
            raise SystemExit(f"Selection manifest lacks {key} provenance")
        expected = {(row.get("path"), row.get("sha256"), row.get("size_bytes")) for row in expected_rows}
        actual = {(row.get("path"), row.get("sha256"), row.get("size_bytes")) for row in actual_rows}
        if expected != actual:
            raise SystemExit(f"H1 selection provenance mismatch for {key}; rerun train-only selection")
    recorded_code = selection.get("code_files")
    if not isinstance(recorded_code, list):
        raise SystemExit("Selection manifest lacks replay code hashes")
    actual_code = {row.get("path"): row for row in current_code_files}
    for expected_row in recorded_code:
        actual_row = actual_code.get(expected_row.get("path"))
        if actual_row is None or (actual_row.get("sha256"), actual_row.get("size_bytes")) != (expected_row.get("sha256"), expected_row.get("size_bytes")):
            raise SystemExit(f"H1 replay code changed since selection: {expected_row.get('path')}; rerun train-only selection")


def load_frozen_selection_manifest(environ=None):
    """Load and validate the train-only top-five manifest required by every mode."""
    env = os.environ if environ is None else environ
    raw_path = str(env.get("H1_SELECTION_MANIFEST", "")).strip()
    if not raw_path:
        raise SystemExit("H1_SELECTION_MANIFEST is required; run the train-only top-five selector first")
    path = Path(raw_path)
    if not path.is_file():
        raise SystemExit(f"H1 selection manifest does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid H1 selection manifest: {exc}") from exc
    if payload.get("schema_version") != 1 or payload.get("selection_protocol") != "h1-top5-train-only-v2":
        raise SystemExit("Unsupported H1 selection manifest schema/protocol")
    if payload.get("selection_status") != "ok":
        raise SystemExit("H1 selection manifest has no valid top-five set; refusing validation")
    strategy_config = payload.get("strategy_config")
    if not isinstance(strategy_config, dict) or strategy_config.get("direction") != "long_only":
        raise SystemExit("H1 runner is long-only; selection manifest must explicitly declare strategy_config.direction=long_only")
    if not isinstance(payload.get("input_files"), dict) or not isinstance(payload.get("code_files"), list):
        raise SystemExit("H1 selection manifest lacks immutable data/code provenance")
    primary = payload.get("primary")
    if not isinstance(primary, list) or len(primary) != 5:
        raise SystemExit("H1 selection manifest must contain exactly five primary symbols")
    symbols = [str(item).strip().upper() for item in primary]
    if any(not item for item in symbols) or len(set(symbols)) != 5:
        raise SystemExit("H1 selection manifest primary symbols must be unique and non-empty")
    allowlist = [
        item.strip().upper()
        for item in str(env.get("H1_SYMBOL_ALLOWLIST", "")).split(",")
        if item.strip()
    ]
    if len(allowlist) != 5 or set(allowlist) != set(symbols):
        raise SystemExit("H1_SYMBOL_ALLOWLIST must exactly match the five symbols in the selection manifest")
    try:
        cutoff = int(payload["training_window"]["cutoff_timestamp_ms"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit("H1 selection manifest lacks a valid training cutoff timestamp") from exc
    if cutoff <= 0:
        raise SystemExit("H1 selection training cutoff must be positive")
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "symbols": sorted(symbols),
        "training_cutoff_timestamp_ms": cutoff,
        "generated_at_utc": payload.get("generated_at_utc"),
        "input_files": payload["input_files"],
        "code_files": payload["code_files"],
    }


def selection_validation_boundary(timestamps):
    """Selection must end before the first explore fold, even in confirm-only mode."""
    if not timestamps:
        raise SystemExit("Cannot validate selection cutoff against an empty H1 timeline")
    return timestamps[int(len(timestamps) * 0.5)]


def validate_selection_cutoff(selection, first_scored_timestamp_ms):
    """Prove the selector's last training candle precedes every validation fold."""
    cutoff = int(selection["training_cutoff_timestamp_ms"])
    first_scored = int(first_scored_timestamp_ms)
    if cutoff >= first_scored:
        raise SystemExit(
            f"H1 selection leakage: training cutoff {cutoff} is not before "
            f"first validation timestamp {first_scored}"
        )


def resolve_validation_design(environ=None):
    """Separate train-only universe selection, exploratory folds and final confirmation."""
    env = os.environ if environ is None else environ
    mode = str(env.get("H1_VALIDATION_MODE", "explore")).strip().lower()
    if mode not in {"explore", "confirm"}:
        raise SystemExit("H1_VALIDATION_MODE must be 'explore' or 'confirm'")
    selection = load_frozen_selection_manifest(env)
    if mode == "explore":
        return {
            "mode": mode,
            "folds": FOLDS[:2],
            "volume_thresholds": list(VOL_THRESHOLDS),
            "breakout_atr_thresholds": list(BREAKOUT_ATR_THRESHOLDS),
            "cost_multipliers": list(COST_MULTIPLIERS),
            "frozen_config": None,
            "selection": selection,
        }
    try:
        volume = float(env["H1_FROZEN_MIN_VOLUME_RATIO"])
        breakout = float(env["H1_FROZEN_MIN_BREAKOUT_ATR"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit(
            "confirm mode requires H1_FROZEN_MIN_VOLUME_RATIO and "
            "H1_FROZEN_MIN_BREAKOUT_ATR from the predeclared research grid"
        ) from exc
    if not math.isfinite(volume) or volume not in VOL_THRESHOLDS:
        raise SystemExit(f"frozen volume threshold must be one of {VOL_THRESHOLDS}")
    if not math.isfinite(breakout) or breakout not in BREAKOUT_ATR_THRESHOLDS:
        raise SystemExit(f"frozen breakout ATR threshold must be one of {BREAKOUT_ATR_THRESHOLDS}")
    return {
        "mode": mode,
        "folds": FOLDS[2:],
        "volume_thresholds": [volume],
        "breakout_atr_thresholds": [breakout],
        "cost_multipliers": list(COST_MULTIPLIERS),
        "frozen_config": {
            "min_volume_ratio": volume,
            "min_breakout_atr": breakout,
            "symbols": selection["symbols"],
            "selection_manifest_sha256": selection["sha256"],
        },
        "selection": selection,
    }


BASE_TAKER_FEE = em.TAKER_FEE
BASE_MAKER_FEE = em.MAKER_FEE
BASE_TAKER_SLIP = em.TAKER_SLIP


@contextmanager
def engine_cost_stress(multiplier):
    """Apply a cost stress only inside one replay; always restore module globals."""
    value = float(multiplier)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("cost multiplier must be finite and positive")
    original = (em.TAKER_FEE, em.MAKER_FEE, em.TAKER_SLIP)
    em.TAKER_FEE = BASE_TAKER_FEE * value
    em.MAKER_FEE = BASE_MAKER_FEE * value
    em.TAKER_SLIP = BASE_TAKER_SLIP * value
    try:
        yield
    finally:
        em.TAKER_FEE, em.MAKER_FEE, em.TAKER_SLIP = original


def round_limit_quote_to_bybit_tick(instrument_spec, price, direction):
    """Round a simulated limit quote to the dated Bybit tick without crossing it."""
    side = "buy" if str(direction).strip().lower() == "long" else "sell"
    return float(instrument_spec.round_price(price, side=side))


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
    trade_kline_dir=None,
):
    """Require funding events and Bybit mark candles aligned to every scored H1 bar."""
    from scripts.validate_funding_coverage import validate_coverage
    from funding_archive_manifest import validate_funding_manifest

    report = validate_coverage(
        funding_dir, mark_price_dir, symbols, trade_kline_dir=trade_kline_dir
    )
    if not report.get("ok"):
        bad = [row for row in report.get("results", []) if row.get("status") != "ok"]
        raise SystemExit(f"Incomplete Bybit funding/mark coverage: {bad[:10]}")
    expected = {int(ts) for ts in h1_timestamps if start_ts <= int(ts) <= end_ts}
    for symbol in symbols:
        funding_path = Path(funding_dir) / f"{symbol}.csv"
        funding_manifest_path = funding_path.with_suffix(funding_path.suffix + ".audit.json")
        manifest_report = validate_funding_manifest(
            funding_path, funding_manifest_path, symbol=symbol,
            required_start_ms=start_ts, required_end_ms=end_ts,
        )
        if not manifest_report.get("ok"):
            raise SystemExit(
                f"Unverified Bybit funding archive for {symbol}: "
                f"{manifest_report.get('errors', manifest_report.get('status'))}"
            )
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
    required = {"symbol", "timestamp_ms", "open", "high", "low", "close", "volume", "turnover"}
    raw = {}
    for path in sorted(root.glob("*.csv")):
        symbol = path.stem.upper()
        candles = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise SystemExit(f"{path}: missing Bybit trade-kline columns {sorted(required)}")
            for line_no, row in enumerate(reader, start=2):
                row_symbol = str(row.get("symbol", "")).strip().upper()
                if row_symbol != symbol:
                    raise SystemExit(
                        f"{path}:{line_no}: row symbol {row_symbol!r} does not match "
                        f"filename symbol {symbol}"
                    )
                try:
                    ts = int(row["timestamp_ms"])
                    op, hi, low, close, volume, turnover = (
                        float(row[key]) for key in
                        ("open", "high", "low", "close", "volume", "turnover")
                    )
                except (TypeError, ValueError, KeyError, OverflowError) as exc:
                    raise SystemExit(f"{path}:{line_no}: invalid Bybit H1 candle: {exc}") from exc
                if ts <= 0 or ts % 3_600_000 != 0:
                    raise SystemExit(
                        f"{path}:{line_no}: Bybit H1 timestamp is not aligned to a UTC hour"
                    )
                values = (op, hi, low, close, volume, turnover)
                if (not all(math.isfinite(value) for value in values)
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

AVERAGE_MONTH_MS = 365.2425 / 12.0 * 24.0 * 60.0 * 60.0 * 1000.0


def geometric_monthly_return_pct(net_pnl, starting_capital, start_ts, end_ts,
                                  bar_interval_ms=3_600_000):
    """Geometric monthly-equivalent return from a cumulative fold result.

    This is a normalized rate, not evidence that every calendar month was
    profitable. The final H1 candle is treated as complete through its close.
    """
    values = (net_pnl, starting_capital)
    if any(not math.isfinite(float(value)) for value in values):
        raise ValueError("net_pnl and starting_capital must be finite")
    if starting_capital <= 0:
        raise ValueError("starting_capital must be positive")
    if (
        isinstance(start_ts, bool) or not isinstance(start_ts, int)
        or isinstance(end_ts, bool) or not isinstance(end_ts, int)
        or isinstance(bar_interval_ms, bool) or not isinstance(bar_interval_ms, int)
        or bar_interval_ms <= 0 or end_ts < start_ts
    ):
        raise ValueError("invalid fold timestamps or bar interval")
    duration_ms = end_ts - start_ts + bar_interval_ms
    duration_months = duration_ms / AVERAGE_MONTH_MS
    final_equity = float(starting_capital) + float(net_pnl)
    if final_equity <= 0:
        monthly_pct = -100.0
    else:
        monthly_pct = (math.pow(final_equity / float(starting_capital),
                                1.0 / duration_months) - 1.0) * 100.0
    return {
        "duration_days": duration_ms / 86_400_000.0,
        "duration_months": duration_months,
        "geometric_monthly_return_pct": monthly_pct,
    }


def run_portfolio_variant(base_candles, symbols, timestamps, fold, start_frac, end_frac,
                          min_vol, min_breakout_atr, cost_multiplier,
                          instrument_specs_dir, risk_tiers_dir,
                          funding_dir, mark_price_dir, kline_dir):
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
            raw_limit_price = float(sig["entry_price"]) * (
                1.0 - ENTRY_OFFSET_BPS / 10000.0
                if str(sig.get("direction", "long")).lower() == "long"
                else 1.0 + ENTRY_OFFSET_BPS / 10000.0
            )
            spec_history = getattr(engine, "instrument_spec_history", None)
            if spec_history is None:
                raise RuntimeError("multi-bar Bybit limit wait requires dated instrument specs")
            spec = spec_history.get_spec(
                sym, int(candle.ts),
                max_age_ms=getattr(
                    engine, "max_instrument_spec_age_ms",
                    30 * 24 * 60 * 60 * 1000,
                ),
            )
            sig["entry_price"] = round_limit_quote_to_bybit_tick(
                spec, raw_limit_price, str(sig.get("direction", "long"))
            )
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
        with engine_cost_stress(cost_multiplier):
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
    monthly_metrics = geometric_monthly_return_pct(
        audit["net_pnl"], STARTING_CAPITAL, start_ts, end_ts,
    )
    return {
        "timeframe": "1h",
        "fold": fold,
        **{key: round(value, 4) for key, value in monthly_metrics.items()},
        "variant": f"vol{min_vol:g}_breakATR{min_breakout_atr:g}_cost{cost_multiplier:g}",
        "cost_multiplier": cost_multiplier,
        "min_volume_ratio": min_vol,
        "min_breakout_atr": min_breakout_atr,
        "symbols": len(symbols),
        "symbol_list": ",".join(symbols),
        "common_h1_bars": len(timestamps),
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


def _manifest_path(path):
    candidate = Path(path).resolve()
    repo_root = Path(__file__).resolve().parents[1]
    try:
        return candidate.relative_to(repo_root).as_posix()
    except ValueError:
        return str(candidate)


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_manifest_record(path):
    source = Path(path)
    stat = source.stat()
    return {
        "path": _manifest_path(source),
        "size_bytes": stat.st_size,
        "sha256": _sha256_file(source),
    }


def _directory_file_manifest(directory, suffixes):
    root = Path(directory)
    if not root.is_dir():
        raise SystemExit(f"Cannot manifest missing input directory: {root}")
    allowed = {suffix.lower() for suffix in suffixes}
    files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in allowed
    )
    if not files:
        raise SystemExit(f"Cannot manifest empty input directory: {root}")
    return [_file_manifest_record(path) for path in files]


def _selected_kline_manifest_record(symbol, path):
    record = _file_manifest_record(path)
    timestamps = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "timestamp_ms" not in reader.fieldnames:
            raise SystemExit(f"{path}: cannot manifest missing timestamp_ms column")
        for line_no, row in enumerate(reader, start=2):
            try:
                timestamps.append(int(row["timestamp_ms"]))
            except (TypeError, ValueError, KeyError) as exc:
                raise SystemExit(
                    f"{path}:{line_no}: invalid timestamp while building run manifest"
                ) from exc
    if not timestamps:
        raise SystemExit(f"{path}: selected Bybit H1 source is empty")
    record.update({
        "symbol": symbol,
        "row_count": len(timestamps),
        "first_timestamp_ms": min(timestamps),
        "last_timestamp_ms": max(timestamps),
    })
    return record


def runtime_provenance():
    """Distinguish the checked-out research code from the workflow-dispatch ref."""
    return {
        "git_commit": os.getenv("H1_RESEARCH_CHECKOUT_SHA") or os.getenv("GITHUB_SHA"),
        "workflow_definition_commit": os.getenv("GITHUB_SHA"),
        "workflow_definition_ref": os.getenv("GITHUB_WORKFLOW_REF") or os.getenv("GITHUB_REF"),
    }


def build_validation_manifest(
    *,
    symbols,
    archives,
    common_timestamps,
    kline_dir,
    funding_dir,
    mark_price_dir,
    instrument_specs_dir,
    risk_tiers_dir,
    result_rows,
    output_csv_path,
    validation_design=None,
):
    """Build an immutable input/code/config manifest for the H1 portfolio report."""
    selected_symbols = sorted(str(symbol).upper() for symbol in symbols)
    if not selected_symbols or len(selected_symbols) != len(set(selected_symbols)):
        raise ValueError("manifest symbols must be non-empty and unique")
    missing_sources = sorted(set(selected_symbols) - set(archives))
    if missing_sources:
        raise ValueError(f"missing selected kline source paths: {missing_sources}")
    timestamps = [int(value) for value in common_timestamps]
    if not timestamps or timestamps != sorted(set(timestamps)):
        raise ValueError("common H1 timestamps must be non-empty, unique and sorted")

    design = validation_design or {
        "mode": "manifest_only_test",
        "folds": FOLDS,
        "volume_thresholds": list(VOL_THRESHOLDS),
        "breakout_atr_thresholds": list(BREAKOUT_ATR_THRESHOLDS),
        "cost_multipliers": list(COST_MULTIPLIERS),
        "frozen_config": None,
        "selection": None,
    }
    folds = []
    for fold, start_fraction, end_fraction in design["folds"]:
        start_index = int(len(timestamps) * start_fraction)
        end_index = int(len(timestamps) * end_fraction)
        if end_index <= start_index:
            raise ValueError(f"fold {fold} has no timestamps in common grid")
        folds.append({
            "fold": fold,
            "start_fraction": start_fraction,
            "end_fraction": end_fraction,
            "start_timestamp_ms": timestamps[start_index],
            "end_timestamp_ms": timestamps[end_index - 1],
            "bar_count": end_index - start_index,
        })

    kline_files = _directory_file_manifest(kline_dir, {".csv"})
    kline_file_paths = {record["path"] for record in kline_files}
    selected_sources = {}
    for symbol in selected_symbols:
        source_path = Path(archives[symbol])
        source_record = _selected_kline_manifest_record(symbol, source_path)
        if source_record["path"] not in kline_file_paths:
            raise ValueError(
                f"selected kline source for {symbol} is outside the manifested kline directory"
            )
        selected_sources[symbol] = source_record

    input_files = {
        "trade_kline": {
            "directory": _manifest_path(kline_dir),
            "all_csv_files": kline_files,
            "selected_sources": selected_sources,
        },
        "funding": {
            "directory": _manifest_path(funding_dir),
            "files": _directory_file_manifest(funding_dir, {".csv", ".json"}),
        },
        "mark_price": {
            "directory": _manifest_path(mark_price_dir),
            "files": _directory_file_manifest(mark_price_dir, {".csv"}),
        },
        "instrument_specs": {
            "directory": _manifest_path(instrument_specs_dir),
            "files": _directory_file_manifest(instrument_specs_dir, {".json"}),
        },
        "risk_tiers": {
            "directory": _manifest_path(risk_tiers_dir),
            "files": _directory_file_manifest(risk_tiers_dir, {".json"}),
        },
    }

    repo_root = Path(__file__).resolve().parents[1]
    code_paths = list(H1_REPLAY_CODE_PATHS) + [
        ".github/workflows/h1-shared-capital-portfolio-validation.yml",
    ]
    code_files = [
        _file_manifest_record(repo_root / relative)
        for relative in code_paths
        if (repo_root / relative).is_file()
    ]

    allowlist = sorted({
        item.strip().upper()
        for item in os.getenv("H1_SYMBOL_ALLOWLIST", "").split(",")
        if item.strip()
    })
    output_record = _file_manifest_record(output_csv_path)
    selection = design.get("selection")
    selection_record = None if selection is None else {
        "path": _manifest_path(selection["path"]),
        "sha256": selection["sha256"],
        "training_cutoff_timestamp_ms": selection["training_cutoff_timestamp_ms"],
        "generated_at_utc": selection["generated_at_utc"],
    }
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run": {
            **runtime_provenance(),
            "workflow_run_id": os.getenv("GITHUB_RUN_ID"),
            "workflow_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
            "python_version": sys.version,
            "platform": platform.platform(),
            "bybit_api_base_url": os.getenv("BYBIT_API_BASE_URL"),
        },
        "data_source": (
            "Official Bybit V5 archive paths; schemas and timestamps validated by the runner. "
            "Hashes identify exact files but do not independently attest remote origin."
        ),
        "universe": {
            "selection_mode": "frozen_train_only_top5",
            "allowlist": allowlist,
            "selected_symbols": selected_symbols,
            "selected_symbol_count": len(selected_symbols),
            "selection_manifest": selection_record,
        },
        "common_h1_grid": {
            "timeframe": "1h",
            "bar_count": len(timestamps),
            "first_timestamp_ms": timestamps[0],
            "last_timestamp_ms": timestamps[-1],
        },
        "folds": folds,
        "strategy_and_execution": {
            "direction": "long_only",
            "strategy": "H1-momentum-breakout",
            "validation_mode": design["mode"],
            "frozen_config": design["frozen_config"],
            "volume_thresholds": design["volume_thresholds"],
            "breakout_atr_thresholds": design["breakout_atr_thresholds"],
            "cost_multipliers": design["cost_multipliers"],
            "entry_offset_bps": ENTRY_OFFSET_BPS,
            "entry_penetration_bps": ENTRY_PENETRATION_BPS,
            "limit_wait_bars": WAIT_BARS,
            "starting_capital_usdt": STARTING_CAPITAL,
            "leverage_mode": "ISOLATED_5X",
            "leverage_val": 5.0,
            "max_concurrent_positions": MAX_CONCURRENT_POSITIONS,
            "max_risk_trade_pct": 1.0,
            "max_portfolio_risk_pct": 2.0,
            "daily_stop_loss_pct": 5.0,
            "emergency_kill_switch_pct": 30.0,
            "max_chase_limit_pct": 1.5,
            "donchian_period": 20,
            "atr_period": 14,
            "stop_atr_mult": 2.5,
            "tp1_r_multiple": 2.0,
            "tp2_r_multiple": 5.0,
            "atr_trail_mult": 3.0,
            "max_hold_bars": 32,
            "maker_entry_and_tp1": True,
            "maker_tp1_and_target": False,
            "base_taker_fee": BASE_TAKER_FEE,
            "base_maker_fee": BASE_MAKER_FEE,
            "base_taker_slippage": BASE_TAKER_SLIP,
        },
        "input_files": input_files,
        "code_files": code_files,
        "outputs": {
            "portfolio_results_csv": output_record,
        },
        "result_metric_definitions": {
            "return_pct": "cumulative net fold return relative to shared starting capital",
            "geometric_monthly_return_pct": (
                "geometric monthly-equivalent rate derived from cumulative fold net return "
                "and exact fold duration; not a claim of positive returns in every calendar month"
            ),
            "duration_days": "inclusive H1 fold duration from first candle open through last candle close",
        },
        "result_rows": result_rows,
    }


def write_validation_manifest(manifest, path):
    target = Path(path)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    return target


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
    design = resolve_validation_design()
    first_scored_timestamp = selection_validation_boundary(timestamps)
    validate_selection_cutoff(design["selection"], first_scored_timestamp)
    if set(design["selection"]["symbols"]) != set(symbols):
        raise SystemExit("Aligned Bybit universe does not exactly match frozen top-five selection manifest")
    repo_root = Path(__file__).resolve().parents[1]
    selection_code_files = [
        _file_manifest_record(repo_root / relative)
        for relative in H1_REPLAY_CODE_PATHS
        if (repo_root / relative).is_file()
    ]
    recorded_universe = design["selection"]["input_files"].get("universe_snapshot")
    if not isinstance(recorded_universe, list) or len(recorded_universe) != 1:
        raise SystemExit("H1 selection manifest must identify exactly one lifecycle universe snapshot")
    universe_path = Path(recorded_universe[0].get("path", ""))
    if not universe_path.is_absolute():
        universe_path = repo_root / universe_path
    universe_path = universe_path.resolve()
    if not universe_path.is_file():
        raise SystemExit(f"H1 lifecycle universe snapshot is missing: {universe_path}")
    try:
        universe_path.relative_to(repo_root)
    except ValueError as exc:
        raise SystemExit("H1 lifecycle universe snapshot must be inside the checked-out repository") from exc
    validate_selection_provenance(
        design["selection"],
        {
            "kline": _directory_file_manifest(kline_dir, {".csv"}),
            "funding": _directory_file_manifest(funding_dir, {".csv"}),
            "mark_price": _directory_file_manifest(mark_price_dir, {".csv"}),
            "instrument_specs": _directory_file_manifest(instrument_specs_dir, {".json"}),
            "risk_tiers": _directory_file_manifest(risk_tiers_dir, {".json"}),
            "universe_snapshot": [_file_manifest_record(universe_path)],
        },
        selection_code_files,
    )
    print(f"Train-only selection manifest={design['selection']['path']} sha256={design['selection']['sha256']}")
    print(f"Validation mode={design['mode']}; folds={[item[0] for item in design['folds']]}; "
          f"volume={design['volume_thresholds']}; breakoutATR={design['breakout_atr_thresholds']}; "
          f"cost stress={design['cost_multipliers']}")
    rows = []
    for fold, start_frac, end_frac in design["folds"]:
        for min_vol in design["volume_thresholds"]:
            for min_breakout in design["breakout_atr_thresholds"]:
                for cost_multiplier in design["cost_multipliers"]:
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
    manifest = build_validation_manifest(
        symbols=symbols,
        archives=archives,
        common_timestamps=timestamps,
        kline_dir=kline_dir,
        funding_dir=funding_dir,
        mark_price_dir=mark_price_dir,
        instrument_specs_dir=instrument_specs_dir,
        risk_tiers_dir=risk_tiers_dir,
        result_rows=rows,
        output_csv_path=path,
        validation_design=design,
    )
    manifest_path = write_validation_manifest(
        manifest, "h1_shared_capital_portfolio_validation_manifest.json"
    )
    print(f"Saved {path}; {len(rows)} portfolio-fold-cost runs. Cost multipliers={COST_MULTIPLIERS}.")
    print(f"Saved reproducibility manifest: {manifest_path}")
    print("CAVEAT: Bybit-native H1 trade OHLCV; OHLC limit penetration is not a real queue/fill model.")
    print("CAVEAT: Funding uses timestamp-aligned Mark-candle open as a settlement-price proxy; fees/slippage are fixed model assumptions.")
    print("CAVEAT: No historical bid/ask, L2 queue priority, partial-fill adverse selection, or account-specific fee tier is modelled.")
    print("CAVEAT: Isolated liquidation is a position-level model; confirm the actual Bybit account mode (UTA vs Classic) before interpreting liquidation results.")


if __name__ == "__main__":
    main()
