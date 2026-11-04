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
import ast
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
from market_structure import trend_label_index, lookup_trend_label
from multibar_limit_wait import evaluate_limit_wait, prepare_signal_for_next_bar_fill

FOLDS = [(1, 0.50, 0.65), (2, 0.65, 0.80), (3, 0.80, 1.00)]
VOL_THRESHOLDS = [1.2, 1.6, 2.0, 2.5]
BREAKOUT_ATR_THRESHOLDS = [0.0, 0.10, 0.25]
VOLUME_LOOKBACK_PERIOD = 20  # held fixed across Donchian20/48 arms
ENTRY_OFFSET_BPS = 20.0
ENTRY_PENETRATION_BPS = 5.0
WAIT_BARS = 3
STARTING_CAPITAL = 10_000.0
LEVERAGE_MODE = "ISOLATED_5X"
LEVERAGE_VAL = 5.0
MAX_CHASE_LIMIT_PCT = 1.5
ACCELERATED_ATR_TRAIL_AFTER_1_5R = False
ENABLE_POST_BREAK_INVALIDATION = False
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


def resolve_h1_replay_code_paths(repo_root=None, seed_paths=None):
    """Resolve the transitive closure of repository-local Python imports.

    The explicit seed list defines replay entry points. Every local module
    imported by those files (including transitive and package imports) is
    added automatically, so a new import cannot silently sit outside the
    frozen selection provenance merely because a maintainer forgot to extend
    a second hand-maintained dependency list.
    """
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    seeds = list(H1_REPLAY_CODE_PATHS if seed_paths is None else seed_paths)
    discovered = set()
    queue = []
    for raw in seeds:
        relative = Path(raw).as_posix()
        candidate = root / relative
        if not candidate.is_file():
            raise SystemExit(f"Missing required H1 replay code seed: {relative}")
        if relative not in discovered:
            discovered.add(relative)
            queue.append(relative)

    def module_candidates(module_name):
        if not module_name:
            return []
        module_path = module_name.replace(".", "/")
        return [module_path + ".py", module_path + "/__init__.py"]

    while queue:
        relative = queue.pop()
        source_path = root / relative
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeError, SyntaxError) as exc:
            raise SystemExit(f"Cannot parse H1 replay dependency {relative}: {exc}") from exc

        parts = Path(relative).with_suffix("").parts
        if parts and parts[-1] == "__init__":
            current_module_parts = parts[:-1]
            package_parts = current_module_parts
        else:
            current_module_parts = parts
            package_parts = parts[:-1]

        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    keep = len(package_parts) - node.level + 1
                    if keep < 0:
                        continue
                    base_parts = package_parts[:keep]
                    if node.module:
                        base_parts += tuple(node.module.split("."))
                    base = ".".join(base_parts)
                else:
                    base = node.module or ""
                if base:
                    imported_modules.add(base)
                for alias in node.names:
                    if alias.name != "*":
                        child = ".".join(part for part in (base, alias.name) if part)
                        if child:
                            imported_modules.add(child)

        local_paths = set()
        for module_name in imported_modules:
            for candidate in module_candidates(module_name):
                if (root / candidate).is_file():
                    local_paths.add(candidate)
            module_parts = module_name.split(".")
            for index in range(1, len(module_parts)):
                package_init = "/".join(module_parts[:index]) + "/__init__.py"
                if (root / package_init).is_file():
                    local_paths.add(package_init)

        for candidate in sorted(local_paths):
            if candidate not in discovered:
                discovered.add(candidate)
                queue.append(candidate)

    return sorted(discovered)



def resolve_ema50_200_gate(environ=None):
    """Opt-in paired comparison; default run remains baseline-only."""
    env = os.environ if environ is None else environ
    raw = str(env.get("H1_EMA50_200_GATE", "0")).strip().lower()
    if raw in {"", "0", "false", "off", "no"}:
        return False
    if raw in {"1", "true", "on", "yes"}:
        return True
    raise SystemExit("H1_EMA50_200_GATE must be one of 0/1, false/true, off/on")



def h1_variant_name(min_vol, min_breakout_atr, cost_multiplier, ema_gate_enabled=False,
                    donchian_period=20):
    """Unambiguous output label for frozen H1 strategy ablations."""
    suffix = "_ema50_200_up" if ema_gate_enabled else ""
    channel = "" if int(donchian_period) == 20 else f"_donchian{int(donchian_period)}"
    return (
        f"vol{min_vol:g}_breakATR{min_breakout_atr:g}_cost{cost_multiplier:g}"
        f"{channel}{suffix}"
    )


def resolve_donchian_variant_modes(environ=None):
    """Opt in to the preregistered three-arm Donchian20/48/EMA experiment."""
    env = os.environ if environ is None else environ
    raw = str(env.get("H1_DONCHIAN48_EMA_ABLATION", "0")).strip().lower()
    if raw in {"", "0", "false", "off", "no"}:
        ema = resolve_ema50_200_gate(env)
        return tuple((20, enabled) for enabled in h1_variant_modes(ema))
    if raw not in {"1", "true", "on", "yes"}:
        raise SystemExit("H1_DONCHIAN48_EMA_ABLATION must be one of 0/1, false/true, off/on")
    if resolve_ema50_200_gate(env):
        raise SystemExit(
            "H1_DONCHIAN48_EMA_ABLATION cannot be combined with H1_EMA50_200_GATE; "
            "the preregistered three-arm design controls its own EMA modes"
        )
    return ((20, False), (48, False), (48, True))


def h1_variant_modes(ema_comparison_enabled):
    """When opted in, run paired baseline and EMA variants on identical folds."""
    return (False, True) if ema_comparison_enabled else (False,)




def build_paired_ema_comparison(result_rows, comparison_enabled):
    """Pair baseline and EMA-gated rows on identical fold/config/cost keys."""
    rows = list(result_rows)
    if not comparison_enabled:
        if any(bool(row.get("ema50_200_gate")) for row in rows):
            raise ValueError("baseline-only manifest contains EMA-gated result rows")
        return {"mode": "baseline_only", "pair_count": 0, "pairs": []}

    baseline = {}
    gated = {}
    for row in rows:
        key = (
            int(row["fold"]),
            int(row.get("donchian_period", 20)),
            float(row["min_volume_ratio"]),
            float(row["min_breakout_atr"]),
            float(row["cost_multiplier"]),
        )
        target = gated if bool(row.get("ema50_200_gate")) else baseline
        if key in target:
            raise ValueError(f"duplicate EMA comparison row for key {key}")
        target[key] = row
    if not gated or set(gated) != set(baseline):
        missing_ema = sorted(set(baseline) - set(gated))
        missing_baseline = sorted(set(gated) - set(baseline))
        raise ValueError(
            "EMA comparison requires exactly paired, identical baseline/EMA key sets; "
            f"missing EMA rows={missing_ema}, missing baseline rows={missing_baseline}"
        )

    pairs = []
    for key in sorted(gated):
        base, candidate = baseline[key], gated[key]
        paired_invariants = (
            "timeframe", "symbol_list", "symbols", "common_h1_bars",
            "test_start_ts", "test_end_ts", "shared_starting_capital",
            "max_concurrent_positions",
        )
        for field in paired_invariants:
            if field not in base or field not in candidate or base[field] != candidate[field]:
                raise ValueError(
                    f"paired EMA portfolios differ in {field!r} for key {key}"
                )
        pairs.append({
            "fold": key[0],
            "donchian_period": key[1],
            "min_volume_ratio": key[2],
            "min_breakout_atr": key[3],
            "cost_multiplier": key[4],
            "baseline_net_pnl": float(base["net_pnl"]),
            "ema_gated_net_pnl": float(candidate["net_pnl"]),
            "delta_net_pnl_ema_minus_baseline": round(
                float(candidate["net_pnl"]) - float(base["net_pnl"]), 6
            ),
            "baseline_trades": int(base["trades"]),
            "ema_gated_trades": int(candidate["trades"]),
            "delta_trades_ema_minus_baseline": (
                int(candidate["trades"]) - int(base["trades"])
            ),
            "baseline_costs": float(base["costs"]),
            "ema_gated_costs": float(candidate["costs"]),
            "delta_costs_ema_minus_baseline": round(
                float(candidate["costs"]) - float(base["costs"]), 6
            ),
            "baseline_profit_factor": float(base["profit_factor"]),
            "ema_gated_profit_factor": float(candidate["profit_factor"]),
            "baseline_expectancy_r": float(base["expectancy_r"]),
            "ema_gated_expectancy_r": float(candidate["expectancy_r"]),
        })
    return {"mode": "paired_baseline_vs_ema50_200_up", "pair_count": len(pairs), "pairs": pairs}


def build_paired_donchian48_comparison(result_rows, enabled):
    """Require and compare the three preregistered shared-capital strategy arms."""
    if not enabled:
        return {"mode": "disabled", "pair_count": 0, "pairs": []}
    rows = list(result_rows)
    indexed = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Donchian comparison rows must be dictionaries")
        if "donchian_period" not in row or "ema50_200_gate" not in row:
            raise ValueError("Donchian comparison row lacks explicit variant metadata")
        period = row["donchian_period"]
        ema_enabled = row["ema50_200_gate"]
        if isinstance(period, bool) or not isinstance(period, int) or period not in (20, 48):
            raise ValueError(f"invalid Donchian comparison period: {period!r}")
        if not isinstance(ema_enabled, bool):
            raise ValueError(f"invalid Donchian EMA gate marker: {ema_enabled!r}")
        mode = (period, ema_enabled)
        key = (
            int(row["fold"]), float(row["min_volume_ratio"]),
            float(row["min_breakout_atr"]), float(row["cost_multiplier"]),
        )
        slot = indexed.setdefault(key, {})
        if mode in slot:
            raise ValueError(f"duplicate Donchian comparison row for {key} mode={mode}")
        slot[mode] = row
    required = {(20, False), (48, False), (48, True)}
    if not indexed or any(set(slot) != required for slot in indexed.values()):
        raise ValueError("Donchian48 experiment requires exactly paired arms: D20 baseline, D48 baseline, D48+EMA")
    pairs = []
    invariants = (
        "timeframe", "symbol_list", "symbols", "common_h1_bars",
        "test_start_ts", "test_end_ts", "shared_starting_capital",
        "max_concurrent_positions", "volume_lookback_period",
    )
    for key in sorted(indexed):
        d20, d48, d48ema = (
            indexed[key][(20, False)], indexed[key][(48, False)], indexed[key][(48, True)]
        )
        for field in invariants:
            if field not in d20 or d20[field] is None:
                raise ValueError(
                    f"Donchian paired portfolios lack required invariant {field!r} for key {key}"
                )
            if any(field not in row or row[field] is None or row[field] != d20[field]
                   for row in (d48, d48ema)):
                raise ValueError(f"Donchian paired portfolios differ in {field!r} for key {key}")
        pairs.append({
            "fold": key[0], "min_volume_ratio": key[1],
            "min_breakout_atr": key[2], "cost_multiplier": key[3],
            "d20_net_pnl": float(d20["net_pnl"]),
            "d48_net_pnl": float(d48["net_pnl"]),
            "d48_ema_net_pnl": float(d48ema["net_pnl"]),
            "delta_d48_vs_d20_net": round(float(d48["net_pnl"]) - float(d20["net_pnl"]), 6),
            "delta_d48_ema_vs_d48_net": round(float(d48ema["net_pnl"]) - float(d48["net_pnl"]), 6),
            "d20_trades": int(d20["trades"]), "d48_trades": int(d48["trades"]),
            "d48_ema_trades": int(d48ema["trades"]),
        })
    return {"mode": "paired_donchian20_vs_donchian48_vs_donchian48_ema", "pair_count": len(pairs), "pairs": pairs}


def build_paired_h1_comparison_summaries(result_rows, design):
    """Build compatible paired summaries for either EMA-only or three-arm D48 mode."""
    rows = list(result_rows)
    donchian48_enabled = bool(design.get("donchian48_ema_ablation_enabled", False))
    ema_enabled = bool(design.get("ema50_200_gate_enabled", False))
    ema_rows = rows
    if donchian48_enabled:
        # The three-arm experiment deliberately has no D20+EMA arm. Its EMA
        # contrast is D48 baseline vs D48+EMA; D20 is the control for the
        # separate three-arm comparison below.
        ema_rows = [row for row in rows if row.get("donchian_period") == 48]
    return {
        "paired_ema_comparison": build_paired_ema_comparison(ema_rows, ema_enabled),
        "paired_donchian48_comparison": build_paired_donchian48_comparison(
            rows, donchian48_enabled
        ),
    }


def build_ema50_200_label_maps(base_candles, symbols, end_idx, first_scored_ts):
    """Precompute causal same-bar EMA50/200 labels with a 1,000-H1-bar burn-in."""
    labels_by_symbol = {}
    for symbol in sorted(symbols):
        if symbol not in base_candles:
            raise SystemExit(f"EMA trend context missing symbol {symbol}")
        rows = list(base_candles[symbol][:end_idx])
        timestamps = [int(candle.ts) for candle in rows]
        try:
            first_scored_index = timestamps.index(int(first_scored_ts))
        except ValueError as exc:
            raise SystemExit(
                f"EMA trend context lacks exact first scored timestamp for {symbol}"
            ) from exc
        if first_scored_index < 1000:
            raise SystemExit(
                f"EMA50/200 requires 1,000 completed H1 pre-roll bars before scoring: "
                f"{symbol} has {first_scored_index}"
            )
        labels_by_symbol[symbol] = trend_label_index(
            rows, fast=50, slow=200, slope=5, burn_in_bars=1000,
            expected_interval_ms=3_600_000,
        )
        # Exact first scored bar must be present; "neutral" is a valid regime,
        # but a missing timestamp is a hard provenance failure.
        lookup_trend_label(labels_by_symbol[symbol], int(first_scored_ts))
    return labels_by_symbol



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

    def index_code_rows(rows, source):
        indexed = {}
        for row in rows:
            if not isinstance(row, dict):
                raise SystemExit(f"Invalid {source} replay code provenance row")
            path = row.get("path")
            sha256 = row.get("sha256")
            size_bytes = row.get("size_bytes")
            if (not isinstance(path, str) or not path.strip()
                    or not isinstance(sha256, str) or not sha256.strip()
                    or isinstance(size_bytes, bool) or not isinstance(size_bytes, int)
                    or size_bytes < 0):
                raise SystemExit(f"Invalid {source} replay code provenance fields")
            if path in indexed:
                raise SystemExit(f"Duplicate {source} replay code provenance path: {path}")
            indexed[path] = row
        return indexed

    expected_code = index_code_rows(recorded_code, "selection manifest")
    actual_code = index_code_rows(current_code_files, "current checkout")
    expected_paths = set(expected_code)
    actual_paths = set(actual_code)
    if expected_paths != actual_paths:
        missing = sorted(expected_paths - actual_paths)
        added = sorted(actual_paths - expected_paths)
        raise SystemExit(
            "H1 replay dependency set changed since selection; rerun train-only selection. "
            f"missing dependencies={missing}, added dependencies={added}"
        )
    for path in sorted(expected_paths):
        expected_row = expected_code[path]
        actual_row = actual_code[path]
        if (actual_row["sha256"], actual_row["size_bytes"]) != (
            expected_row["sha256"], expected_row["size_bytes"]
        ):
            raise SystemExit(
                f"H1 replay code changed since selection: {path}; rerun train-only selection"
            )


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


def resolve_frozen_strategy_mode(env, strategy_modes):
    """Require the confirm run's explicit frozen arm-set to match its toggles."""
    names = {
        "d20_baseline": ((20, False),),
        "d20_ema50_200": ((20, False), (20, True)),
        "d20_d48_d48_ema": ((20, False), (48, False), (48, True)),
    }
    selected = str(env.get("H1_FROZEN_STRATEGY_MODE", "")).strip().lower()
    if selected not in names:
        raise SystemExit(
            "confirm mode requires H1_FROZEN_STRATEGY_MODE: "
            "d20_baseline, d20_ema50_200, or d20_d48_d48_ema"
        )
    if tuple(strategy_modes) != names[selected]:
        raise SystemExit(
            f"frozen strategy mode {selected!r} does not match selected arm set "
            f"{tuple(strategy_modes)!r}"
        )
    return selected


def resolve_validation_design(environ=None):
    """Separate train-only universe selection, exploratory folds and final confirmation."""
    env = os.environ if environ is None else environ
    mode = str(env.get("H1_VALIDATION_MODE", "explore")).strip().lower()
    if mode not in {"explore", "confirm"}:
        raise SystemExit("H1_VALIDATION_MODE must be 'explore' or 'confirm'")
    selection = load_frozen_selection_manifest(env)
    strategy_modes = resolve_donchian_variant_modes(env)
    if mode == "explore":
        return {
            "mode": mode,
            "folds": FOLDS[:2],
            "volume_thresholds": list(VOL_THRESHOLDS),
            "breakout_atr_thresholds": list(BREAKOUT_ATR_THRESHOLDS),
            "cost_multipliers": list(COST_MULTIPLIERS),
            "strategy_modes": strategy_modes,
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
    frozen_strategy_mode = resolve_frozen_strategy_mode(env, strategy_modes)
    return {
        "mode": mode,
        "folds": FOLDS[2:],
        "volume_thresholds": [volume],
        "breakout_atr_thresholds": [breakout],
        "cost_multipliers": list(COST_MULTIPLIERS),
        "strategy_modes": strategy_modes,
        "frozen_config": {
            "strategy_mode": frozen_strategy_mode,
            "strategy_modes": [
                {"donchian_period": period, "ema50_200_gate": ema}
                for period, ema in strategy_modes
            ],
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


def resolve_market_state_skew_budget(environ=None):
    """Read an explicit instrument/risk snapshot skew budget; never invent a default."""
    env = os.environ if environ is None else environ
    raw = env.get("BYBIT_MAX_MARKET_STATE_SKEW_MS")
    if raw is None or not str(raw).strip():
        return None
    value = str(raw).strip()
    if not value.isdecimal():
        raise SystemExit("BYBIT_MAX_MARKET_STATE_SKEW_MS must be a non-negative integer")
    return int(value)


def run_portfolio_variant(base_candles, symbols, timestamps, fold, start_frac, end_frac,
                          min_vol, min_breakout_atr, cost_multiplier,
                          instrument_specs_dir, risk_tiers_dir,
                          funding_dir, mark_price_dir, kline_dir,
                          ema_trend_labels_by_symbol=None, donchian_period=20):
    n = len(timestamps)
    start_idx, end_idx = int(n * start_frac), int(n * end_frac)
    start_ts, end_ts = timestamps[start_idx], timestamps[end_idx - 1]
    # Require as-of exchange metadata throughout the actual scored fold. A
    # present-day snapshot must never be silently applied to older candles.
    # The final H1 timestamp is the candle OPEN. Replay accounting (funding,
    # liquidation tier lookup and final close) runs through its CLOSE boundary.
    fold_close_ts = end_ts + 3_600_000
    validate_snapshot_history_coverage(
        instrument_specs_dir, risk_tiers_dir, start_ts, fold_close_ts
    )
    validate_funding_mark_coverage(
        funding_dir, mark_price_dir, symbols, timestamps, start_ts, fold_close_ts,
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
        max_market_state_skew_ms=resolve_market_state_skew_budget(),
    )
    cfg = engine.cfg
    cfg.bot_version = (
        f"h1-portfolio-d{int(donchian_period)}-v{min_vol:g}-b{min_breakout_atr:g}-cost{cost_multiplier:g}"
        f"{'-ema50_200' if ema_trend_labels_by_symbol is not None else ''}"
    )
    cfg.timeframe = "1h"
    cfg.active_trading_pool = list(symbols)
    cfg.capital_usdt = STARTING_CAPITAL
    cfg.leverage_mode = LEVERAGE_MODE
    cfg.leverage_val = LEVERAGE_VAL
    cfg.max_risk_trade_pct = 1.0
    cfg.max_portfolio_risk_pct = 2.0
    cfg.max_concurrent_positions = MAX_CONCURRENT_POSITIONS
    cfg.max_chase_limit_pct = MAX_CHASE_LIMIT_PCT
    cfg.accelerated_atr_trail_after_1_5r = ACCELERATED_ATR_TRAIL_AFTER_1_5R
    cfg.enable_post_break_invalidation = ENABLE_POST_BREAK_INVALIDATION
    cfg.daily_stop_loss_pct = 5.0
    cfg.emergency_kill_switch_pct = 30.0
    cfg.donchian_period = int(donchian_period)
    cfg.volume_lookback_period = VOLUME_LOOKBACK_PERIOD
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

    if ema_trend_labels_by_symbol is not None:
        missing_label_maps = sorted(set(symbols).difference(ema_trend_labels_by_symbol))
        if missing_label_maps:
            raise ValueError(f"EMA trend context missing symbol maps: {missing_label_maps}")

    core = em.QuantStrategyCore
    original_eval = core.evaluate_signal

    def wrapped_eval(sym, bars, conf):
        if not bars or not (start_ts <= bars[-1].ts <= end_ts):
            return None
        sig = original_eval(sym, bars, conf)
        if sig is None:
            return None
        if ema_trend_labels_by_symbol is not None:
            label_map = ema_trend_labels_by_symbol.get(sym)
            if not isinstance(label_map, dict):
                raise RuntimeError(f"EMA trend context for {sym} is unavailable")
            label = lookup_trend_label(label_map, int(bars[-1].ts))
            if label != "up":
                return None
        if str(sig.get("direction", "")).lower() != "long":
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
            tier_history = getattr(engine, "risk_tier_history", None)
            if spec_history is None or tier_history is None:
                raise RuntimeError(
                    "multi-bar Bybit limit wait requires dated instrument and risk-tier histories"
                )
            market_state = em.get_linear_market_state(
                spec_history, tier_history, sym, int(candle.ts),
                max_snapshot_skew_ms=getattr(engine, "max_market_state_skew_ms", None),
                max_instrument_age_ms=getattr(
                    engine, "max_instrument_spec_age_ms",
                    30 * 24 * 60 * 60 * 1000,
                ),
                max_risk_tier_age_ms=getattr(
                    engine, "max_risk_tier_age_ms",
                    30 * 24 * 60 * 60 * 1000,
                ),
            )
            spec = market_state.instrument_spec
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
            open_price=float(candle.open),
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
        "variant": h1_variant_name(
            min_vol, min_breakout_atr, cost_multiplier,
            ema_gate_enabled=ema_trend_labels_by_symbol is not None,
            donchian_period=donchian_period,
        ),
        "donchian_period": int(donchian_period),
        "volume_lookback_period": VOLUME_LOOKBACK_PERIOD,
        "ema50_200_gate": ema_trend_labels_by_symbol is not None,
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
    code_files = [
        _file_manifest_record(repo_root / relative)
        for relative in resolve_h1_replay_code_paths(repo_root)
    ]
    workflow_path = repo_root / ".github/workflows/h1-shared-capital-portfolio-validation.yml"
    if not workflow_path.is_file():
        raise SystemExit("Missing required H1 validation workflow definition")
    code_files.append(_file_manifest_record(workflow_path))

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
    paired_summaries = build_paired_h1_comparison_summaries(result_rows, design)
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
            "ema50_200_gate": {
                "comparison_mode": (
                    "paired_baseline_vs_ema50_200_up"
                    if bool(design.get("ema50_200_gate_enabled", False))
                    else "baseline_only"
                ),
                "variants": (
                    ["baseline", "ema50_200_up"]
                    if bool(design.get("ema50_200_gate_enabled", False))
                    else ["baseline"]
                ),
                "fast_period": 50,
                "slow_period": 200,
                "slow_slope_lookback": 5,
                "burn_in_bars": 1000,
                "label_timestamp": "same completed H1 candle open timestamp",
                "allowed_label_for_long": "up",
            },
            "frozen_config": design["frozen_config"],
            "volume_thresholds": design["volume_thresholds"],
            "breakout_atr_thresholds": design["breakout_atr_thresholds"],
            "cost_multipliers": design["cost_multipliers"],
            "entry_offset_bps": ENTRY_OFFSET_BPS,
            "entry_penetration_bps": ENTRY_PENETRATION_BPS,
            "limit_wait_bars": WAIT_BARS,
            "starting_capital_usdt": STARTING_CAPITAL,
            "leverage_mode": LEVERAGE_MODE,
            "leverage_val": LEVERAGE_VAL,
            "max_concurrent_positions": MAX_CONCURRENT_POSITIONS,
            "max_risk_trade_pct": 1.0,
            "max_portfolio_risk_pct": 2.0,
            "daily_stop_loss_pct": 5.0,
            "emergency_kill_switch_pct": 30.0,
            "max_chase_limit_pct": MAX_CHASE_LIMIT_PCT,
            "accelerated_atr_trail_after_1_5r": ACCELERATED_ATR_TRAIL_AFTER_1_5R,
            "enable_post_break_invalidation": ENABLE_POST_BREAK_INVALIDATION,
            "donchian_period": int(design.get("primary_donchian_period", 20)),
            "volume_lookback_period": VOLUME_LOOKBACK_PERIOD,
            "donchian_variant_modes": design.get(
                "donchian_variant_modes", [{"donchian_period": 20, "ema50_200_gate": False}]
            ),
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
        "paired_ema_comparison": paired_summaries["paired_ema_comparison"],
        "paired_donchian48_comparison": paired_summaries["paired_donchian48_comparison"],
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
    strategy_modes = design["strategy_modes"]
    ema_gate_enabled = any(use_ema for _, use_ema in strategy_modes)
    design["ema50_200_gate_enabled"] = ema_gate_enabled
    design["donchian48_ema_ablation_enabled"] = (
        strategy_modes == ((20, False), (48, False), (48, True))
    )
    design["donchian_variant_modes"] = [
        {"donchian_period": period, "ema50_200_gate": use_ema}
        for period, use_ema in strategy_modes
    ]
    first_scored_timestamp = selection_validation_boundary(timestamps)
    validate_selection_cutoff(design["selection"], first_scored_timestamp)
    if set(design["selection"]["symbols"]) != set(symbols):
        raise SystemExit("Aligned Bybit universe does not exactly match frozen top-five selection manifest")
    repo_root = Path(__file__).resolve().parents[1]
    selection_code_files = [
        _file_manifest_record(repo_root / relative)
        for relative in resolve_h1_replay_code_paths(repo_root)
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
          f"cost stress={design['cost_multipliers']}; strategy modes={design['donchian_variant_modes']}")
    rows = []
    for fold, start_frac, end_frac in design["folds"]:
        fold_start_index = int(len(timestamps) * start_frac)
        fold_end_index = int(len(timestamps) * end_frac)
        fold_ema_labels = (
            build_ema50_200_label_maps(
                datasets, symbols, fold_end_index, timestamps[fold_start_index],
            )
            if ema_gate_enabled else None
        )
        for min_vol in design["volume_thresholds"]:
            for min_breakout in design["breakout_atr_thresholds"]:
                for cost_multiplier in design["cost_multipliers"]:
                    for donchian_period, use_ema_gate in strategy_modes:
                        result = run_portfolio_variant(
                            datasets, symbols, timestamps, fold, start_frac, end_frac,
                            min_vol, min_breakout, cost_multiplier,
                            instrument_specs_dir, risk_tiers_dir,
                            funding_dir, mark_price_dir, kline_dir,
                            ema_trend_labels_by_symbol=(
                                fold_ema_labels if use_ema_gate else None
                            ),
                            donchian_period=donchian_period,
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
