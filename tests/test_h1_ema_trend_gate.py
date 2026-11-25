"""Deterministic tests for opt-in full-history EMA50/200 H1 gating."""
from pathlib import Path
import json
import tempfile
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_h1_shared_capital_portfolio_validation import (
    ACCELERATED_ATR_TRAIL_AFTER_1_5R, ENABLE_POST_BREAK_INVALIDATION,
    LEVERAGE_MODE, LEVERAGE_VAL, MAX_CHASE_LIMIT_PCT,
    build_ema50_200_label_maps, build_paired_ema_comparison,
    build_paired_donchian48_comparison, build_paired_h1_comparison_summaries,
    resolve_volume_lookback_period,
    resolve_donchian_variant_modes,
    h1_variant_modes, h1_variant_name, resolve_ema50_200_gate,
    load_frozen_selection_manifest,
)
import Bybit_Trading_Engine_v14_research as em
from market_structure import lookup_trend_label

H1_MS = 3_600_000


def make_rows(count):
    rows = []
    for i in range(count):
        close = 100.0 + i * 0.25
        rows.append(SimpleNamespace(
            ts=(i + 1) * H1_MS,
            open=close - 0.1,
            high=close + 0.2,
            low=close - 0.2,
            close=close,
            volume=100.0,
        ))
    return rows


def test_h1_execution_risk_settings_are_explicitly_frozen():
    assert LEVERAGE_MODE == "ISOLATED_5X"
    assert LEVERAGE_VAL == 5.0
    assert MAX_CHASE_LIMIT_PCT == 1.5
    assert ACCELERATED_ATR_TRAIL_AFTER_1_5R is False
    assert ENABLE_POST_BREAK_INVALIDATION is False


def test_btc_single_symbol_manifest_mode_is_separate_and_fail_closed():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "btc.json"
        path.write_text(json.dumps({
            "schema_version": 1,
            "selection_protocol": "h1-btc-single-symbol-v1",
            "selection_status": "ok",
            "generated_at_utc": "2026-11-25T00:00:00Z",
            "strategy_config": {"direction": "long_only", "symbol": "BTCUSDT"},
            "training_window": {"cutoff_timestamp_ms": 1000},
            "input_files": {key: [] for key in ("kline", "funding", "mark_price", "instrument_specs", "risk_tiers", "universe_snapshot")},
            "code_files": [],
            "primary": ["BTCUSDT"],
        }), encoding="utf-8")
        env = {
            "H1_SELECTION_MODE": "btc_single",
            "H1_SELECTION_MANIFEST": str(path),
            "H1_SYMBOL_ALLOWLIST": "BTCUSDT",
        }
        selection = load_frozen_selection_manifest(env)
        assert selection["selection_mode"] == "btc_single"
        assert selection["symbols"] == ["BTCUSDT"]
        env["H1_SYMBOL_ALLOWLIST"] = "BTCUSDT,ETHUSDT"
        try:
            load_frozen_selection_manifest(env)
        except SystemExit as exc:
            assert "exactly match" in str(exc)
        else:
            raise AssertionError("BTC-only manifest must reject additional symbols")


def test_ema50_200_gate_is_explicitly_opt_in_and_rejects_invalid_values():
    assert resolve_ema50_200_gate({}) is False
    assert resolve_ema50_200_gate({"H1_EMA50_200_GATE": "0"}) is False
    assert resolve_ema50_200_gate({"H1_EMA50_200_GATE": "off"}) is False
    assert resolve_ema50_200_gate({"H1_EMA50_200_GATE": "1"}) is True
    assert resolve_ema50_200_gate({"H1_EMA50_200_GATE": "true"}) is True
    try:
        resolve_ema50_200_gate({"H1_EMA50_200_GATE": "maybe"})
    except SystemExit as exc:
        assert "H1_EMA50_200_GATE" in str(exc)
    else:
        raise AssertionError("invalid EMA gate configuration must fail closed")

    baseline = h1_variant_name(1.6, 0.1, 2.0, False)
    gated = h1_variant_name(1.6, 0.1, 2.0, True)
    assert baseline == "vol1.6_breakATR0.1_cost2"
    assert gated == "vol1.6_breakATR0.1_cost2_ema50_200_up"
    assert baseline != gated
    assert h1_variant_modes(False) == (False,)
    assert h1_variant_modes(True) == (False, True)
    assert LEVERAGE_MODE == "ISOLATED_5X"
    assert LEVERAGE_VAL == 5.0




def test_paired_ema_comparison_matches_identical_configs_and_costs():
    def row(gated, net, trades, costs):
        return {
            "fold": 1,
            "min_volume_ratio": 1.6,
            "min_breakout_atr": 0.1,
            "cost_multiplier": 2.0,
            "ema50_200_gate": gated,
            "timeframe": "1h",
            "symbol_list": "BTCUSDT;ETHUSDT;SOLUSDT;XRPUSDT;BNBUSDT",
            "symbols": 5,
            "common_h1_bars": 4000,
            "test_start_ts": 1_000_000,
            "test_end_ts": 2_000_000,
            "shared_starting_capital": 10_000.0,
            "max_concurrent_positions": 5,
        "volume_lookback_period": 20,
            "net_pnl": net,
            "trades": trades,
            "costs": costs,
            "profit_factor": 0.9 if gated else 0.8,
            "expectancy_r": -0.02 if gated else -0.05,
        }

    result = build_paired_ema_comparison(
        [row(False, -100.0, 40, 50.0), row(True, -60.0, 25, 30.0)],
        comparison_enabled=True,
    )
    assert result["mode"] == "paired_baseline_vs_ema50_200_up"
    assert result["pair_count"] == 1
    pair = result["pairs"][0]
    assert pair["delta_net_pnl_ema_minus_baseline"] == 40.0
    assert pair["delta_trades_ema_minus_baseline"] == -15
    assert pair["delta_costs_ema_minus_baseline"] == -20.0



def test_paired_ema_comparison_rejects_different_baskets_or_windows():
    baseline = {
        "fold": 1, "min_volume_ratio": 1.6, "min_breakout_atr": 0.1,
        "cost_multiplier": 2.0, "ema50_200_gate": False,
        "timeframe": "1h", "symbol_list": "BTCUSDT;ETHUSDT",
        "symbols": 2, "common_h1_bars": 4000,
        "test_start_ts": 1_000_000, "test_end_ts": 2_000_000,
        "shared_starting_capital": 10_000.0, "max_concurrent_positions": 5,
        "volume_lookback_period": 20,
        "net_pnl": -100.0, "trades": 40, "costs": 50.0,
        "profit_factor": 0.8, "expectancy_r": -0.05,
    }
    candidate = dict(baseline)
    candidate["ema50_200_gate"] = True
    candidate["symbol_list"] = "BTCUSDT;SOLUSDT"
    try:
        build_paired_ema_comparison([baseline, candidate], comparison_enabled=True)
    except ValueError as exc:
        assert "symbol_list" in str(exc)
    else:
        raise AssertionError("paired variants must use the identical selected basket")



def test_paired_ema_comparison_fails_closed_for_unpaired_rows():
    baseline = {
        "fold": 1, "min_volume_ratio": 1.6, "min_breakout_atr": 0.1,
        "cost_multiplier": 2.0, "ema50_200_gate": False,
        "net_pnl": -100.0, "trades": 40, "costs": 50.0,
        "profit_factor": 0.8, "expectancy_r": -0.05,
    }
    try:
        build_paired_ema_comparison([baseline], comparison_enabled=True)
    except ValueError as exc:
        assert "exactly paired" in str(exc)
    else:
        raise AssertionError("missing EMA comparison leg must fail closed")



def test_paired_ema_comparison_rejects_unmatched_extra_baseline_rows():
    def row(fold, gated):
        return {
            "fold": fold, "min_volume_ratio": 1.6, "min_breakout_atr": 0.1,
            "cost_multiplier": 2.0, "ema50_200_gate": gated,
            "timeframe": "1h", "symbol_list": "BTCUSDT;ETHUSDT",
            "symbols": 2, "common_h1_bars": 4000,
            "test_start_ts": 1_000_000, "test_end_ts": 2_000_000,
            "shared_starting_capital": 10_000.0, "max_concurrent_positions": 5,
        "volume_lookback_period": 20,
            "net_pnl": -100.0, "trades": 40, "costs": 50.0,
            "profit_factor": 0.8, "expectancy_r": -0.05,
        }

    rows = [row(1, False), row(1, True), row(2, False)]
    try:
        build_paired_ema_comparison(rows, comparison_enabled=True)
    except ValueError as exc:
        assert "identical baseline/EMA key sets" in str(exc)
        assert "missing EMA rows" in str(exc)
    else:
        raise AssertionError("an unmatched extra baseline row must fail closed")


def test_ema_gate_precomputes_full_history_and_uses_exact_scored_timestamp():
    rows = make_rows(1_100)
    first_scored_ts = rows[1_000].ts
    labels = build_ema50_200_label_maps(
        {"BTCUSDT": rows}, ["BTCUSDT"], len(rows), first_scored_ts,
    )
    assert lookup_trend_label(labels["BTCUSDT"], first_scored_ts) == "up"
    assert lookup_trend_label(labels["BTCUSDT"], rows[999].ts) == "neutral"
    try:
        lookup_trend_label(labels["BTCUSDT"], rows[-1].ts + H1_MS)
    except KeyError:
        pass
    else:
        raise AssertionError("a non-existent timestamp must not receive a nearest label")


def test_ema_gate_fails_closed_without_1000_pre_roll_bars():
    rows = make_rows(1_100)
    try:
        build_ema50_200_label_maps(
            {"BTCUSDT": rows}, ["BTCUSDT"], len(rows), rows[999].ts,
        )
    except SystemExit as exc:
        assert "1,000 completed H1 pre-roll bars" in str(exc)
    else:
        raise AssertionError("scoring before the full EMA seed burn-in must fail closed")


def test_ema_gate_fails_closed_for_missing_symbol_or_history():
    rows = make_rows(1_100)
    try:
        build_ema50_200_label_maps({}, ["BTCUSDT"], 1_100, rows[1_000].ts)
    except SystemExit as exc:
        assert "missing symbol" in str(exc)
    else:
        raise AssertionError("missing symbol history must fail closed")

    try:
        build_ema50_200_label_maps(
            {"BTCUSDT": rows}, ["BTCUSDT"], 1_000, rows[1_000].ts,
        )
    except SystemExit as exc:
        assert "exact first scored timestamp" in str(exc)
    else:
        raise AssertionError("missing exact scored timestamp must fail closed")


def test_ema_gate_rejects_non_contiguous_h1_history():
    rows = make_rows(1_100)
    rows[500].ts += 1
    try:
        build_ema50_200_label_maps(
            {"BTCUSDT": rows}, ["BTCUSDT"], len(rows), rows[1_000].ts,
        )
    except ValueError as exc:
        assert "contiguous" in str(exc)
    else:
        raise AssertionError("H1 gaps must not be interpreted as consecutive EMA bars")




def test_donchian48_ablation_is_opt_in_and_freezes_exact_three_arms():
    assert resolve_donchian_variant_modes({}) == ((20, False),)
    assert resolve_donchian_variant_modes({"H1_EMA50_200_GATE": "1"}) == ((20, False), (20, True))
    assert resolve_donchian_variant_modes({"H1_DONCHIAN48_EMA_ABLATION": "1"}) == (
        (20, False), (48, False), (48, True)
    )
    try:
        resolve_donchian_variant_modes({
            "H1_DONCHIAN48_EMA_ABLATION": "1",
            "H1_EMA50_200_GATE": "1",
        })
    except SystemExit as exc:
        assert "cannot be combined" in str(exc)
    else:
        raise AssertionError("overlapping EMA experiment flags must fail closed")
    assert h1_variant_name(1.6, 0.1, 2.0, False, 20) == "vol1.6_breakATR0.1_cost2"
    assert h1_variant_name(1.6, 0.1, 2.0, False, 48) == "vol1.6_breakATR0.1_cost2_donchian48"


def test_paired_donchian48_comparison_requires_three_exact_arms():
    base = {
        "fold": 1, "min_volume_ratio": 1.6, "min_breakout_atr": 0.1,
        "cost_multiplier": 2.0, "timeframe": "1h",
        "symbol_list": "BTCUSDT", "symbols": 1,
        "common_h1_bars": 4000, "test_start_ts": 1_000_000,
        "test_end_ts": 2_000_000, "shared_starting_capital": 10_000.0,
        "max_concurrent_positions": 5,
        "volume_lookback_period": 20, "net_pnl": -100.0,
        "trades": 40, "ema50_200_gate": False, "donchian_period": 20,
    }
    rows = []
    for period, ema, net in ((20, False, -100.0), (48, False, -60.0), (48, True, -30.0)):
        row = dict(base, donchian_period=period, ema50_200_gate=ema, volume_lookback_period=period, net_pnl=net)
        rows.append(row)
    result = build_paired_donchian48_comparison(rows, enabled=True)
    assert result["pair_count"] == 1
    assert result["pairs"][0]["delta_d48_vs_d20_net"] == 40.0
    assert result["pairs"][0]["delta_d48_ema_vs_d48_net"] == 30.0
    try:
        build_paired_donchian48_comparison(rows[:2], enabled=True)
    except ValueError as exc:
        assert "exactly paired arms" in str(exc)
    else:
        raise AssertionError("missing Donchian arm must fail closed")


def test_paired_donchian48_rejects_missing_shared_invariant():
    base = {
        "fold": 1, "min_volume_ratio": 1.6, "min_breakout_atr": 0.1,
        "cost_multiplier": 2.0, "timeframe": "1h",
        "symbol_list": "BTCUSDT", "symbols": 1,
        "common_h1_bars": 4000, "test_end_ts": 2_000_000,
        "shared_starting_capital": 10_000.0, "max_concurrent_positions": 5,
        "volume_lookback_period": 20,
        "net_pnl": -100.0, "trades": 40,
    }
    rows = [
        dict(base, donchian_period=period, ema50_200_gate=ema, volume_lookback_period=period)
        for period, ema in ((20, False), (48, False), (48, True))
    ]
    try:
        build_paired_donchian48_comparison(rows, enabled=True)
    except ValueError as exc:
        assert "lack required invariant 'test_start_ts'" in str(exc)
    else:
        raise AssertionError("missing shared portfolio boundary must fail closed")


def test_paired_donchian48_rejects_missing_or_invalid_arm_metadata():
    base = {
        "fold": 1, "min_volume_ratio": 1.6, "min_breakout_atr": 0.1,
        "cost_multiplier": 2.0, "timeframe": "1h",
        "symbol_list": "BTCUSDT", "symbols": 1,
        "common_h1_bars": 4000, "test_start_ts": 1_000_000,
        "test_end_ts": 2_000_000, "shared_starting_capital": 10_000.0,
        "max_concurrent_positions": 5,
        "volume_lookback_period": 20, "net_pnl": -100.0, "trades": 40,
    }
    valid_rows = [
        dict(base, donchian_period=period, ema50_200_gate=ema, volume_lookback_period=period)
        for period, ema in ((20, False), (48, False), (48, True))
    ]
    missing_period = [dict(row) for row in valid_rows]
    missing_period[0].pop("donchian_period")
    invalid_ema = [dict(row) for row in valid_rows]
    invalid_ema[2]["ema50_200_gate"] = "true"

    for rows, expected in (
        (missing_period, "lacks explicit variant metadata"),
        (invalid_ema, "invalid Donchian EMA gate marker"),
    ):
        try:
            build_paired_donchian48_comparison(rows, enabled=True)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("missing or invalid arm metadata must fail closed")


def test_volume_lookback_is_resolved_per_registered_donchian_arm():
    assert resolve_volume_lookback_period(20) == 20
    assert resolve_volume_lookback_period(48) == 48
    for invalid in (True, 20.0, "48", 96):
        try:
            resolve_volume_lookback_period(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid Donchian period accepted: {invalid!r}")


def test_donchian_arms_use_their_own_volume_lookback():
    cfg = em.BotConfig()
    cfg.timeframe = "1h"
    cfg.donchian_period = 48
    cfg.volume_lookback_period = 48
    cfg.atr_period = 14
    cfg.min_volume_ratio = 1.6
    cfg.active_trading_pool = ["BTCUSDT"]

    history = []
    for index in range(49):
        history.append(em.Candle(
            ts=(index + 1) * H1_MS,
            open=100.0,
            high=120.0 if index < 29 else 101.0,
            low=99.0,
            close=100.0,
            volume=500.0 if index < 29 else 100.0,
        ))
    signal_candle = em.Candle(
        ts=50 * H1_MS, open=120.5, high=122.0, low=120.0,
        close=121.0, volume=300.0,
    )
    candles = history + [signal_candle]

    hi20, lo20, avg20 = em.QuantStrategyCore.compute_donchian_and_volume(
        history, 20, volume_period=20,
    )
    hi48, lo48, avg48 = em.QuantStrategyCore.compute_donchian_and_volume(
        history, 48, volume_period=48,
    )
    assert (hi20, lo20) != (hi48, lo48)
    assert avg20 == 100.0
    assert avg48 > avg20

    signals = []
    for period in (20, 48):
        cfg.donchian_period = period
        cfg.volume_lookback_period = period
        signal = em.QuantStrategyCore.evaluate_signal("BTCUSDT", candles, cfg)
        signals.append(signal)
    assert signals[0] is not None
    assert signals[1] is None


def test_paired_donchian48_rejects_changed_volume_lookback():
    base = {
        "fold": 1, "min_volume_ratio": 1.6, "min_breakout_atr": 0.1,
        "cost_multiplier": 2.0, "timeframe": "1h",
        "symbol_list": "BTCUSDT", "symbols": 1,
        "common_h1_bars": 4000, "test_start_ts": 1_000_000,
        "test_end_ts": 2_000_000, "shared_starting_capital": 10_000.0,
        "max_concurrent_positions": 5, "volume_lookback_period": 20,
        "net_pnl": -100.0, "trades": 40,
    }
    rows = [
        dict(base, donchian_period=period, ema50_200_gate=ema)
        for period, ema in ((20, False), (48, False), (48, True))
    ]
    rows[1]["volume_lookback_period"] = 48
    try:
        build_paired_donchian48_comparison(rows, enabled=True)
    except ValueError as exc:
        assert "volume lookbacks 20/48/48" in str(exc)
    else:
        raise AssertionError("Donchian arms must share the same volume lookback")


def test_three_arm_donchian48_manifest_pairs_ema_only_within_d48():
    base = {
        "fold": 1, "min_volume_ratio": 1.6, "min_breakout_atr": 0.1,
        "cost_multiplier": 2.0, "timeframe": "1h",
        "symbol_list": "BTCUSDT", "symbols": 1,
        "common_h1_bars": 4000, "test_start_ts": 1_000_000,
        "test_end_ts": 2_000_000, "shared_starting_capital": 10_000.0,
        "max_concurrent_positions": 5, "volume_lookback_period": 20,
        "net_pnl": -100.0, "trades": 40, "costs": 100.0,
        "profit_factor": 0.8, "expectancy_r": -0.1,
    }
    rows = [
        dict(base, donchian_period=20, ema50_200_gate=False, volume_lookback_period=20, net_pnl=-100.0),
        dict(base, donchian_period=48, ema50_200_gate=False, volume_lookback_period=48, net_pnl=-60.0),
        dict(base, donchian_period=48, ema50_200_gate=True, volume_lookback_period=48, net_pnl=-30.0),
    ]
    summaries = build_paired_h1_comparison_summaries(rows, {
        "ema50_200_gate_enabled": True,
        "donchian48_ema_ablation_enabled": True,
    })
    assert summaries["paired_ema_comparison"]["pair_count"] == 1
    assert summaries["paired_ema_comparison"]["pairs"][0]["baseline_net_pnl"] == -60.0
    assert summaries["paired_ema_comparison"]["pairs"][0]["ema_gated_net_pnl"] == -30.0
    assert summaries["paired_donchian48_comparison"]["pair_count"] == 1
    assert summaries["paired_donchian48_comparison"]["pairs"][0]["d20_net_pnl"] == -100.0


if __name__ == "__main__":
    tests = [
        test_h1_execution_risk_settings_are_explicitly_frozen,
        test_ema50_200_gate_is_explicitly_opt_in_and_rejects_invalid_values,
        test_paired_ema_comparison_matches_identical_configs_and_costs,
        test_paired_ema_comparison_rejects_different_baskets_or_windows,
        test_paired_ema_comparison_fails_closed_for_unpaired_rows,
        test_paired_ema_comparison_rejects_unmatched_extra_baseline_rows,
        test_ema_gate_precomputes_full_history_and_uses_exact_scored_timestamp,
        test_ema_gate_fails_closed_without_1000_pre_roll_bars,
        test_ema_gate_fails_closed_for_missing_symbol_or_history,
        test_ema_gate_rejects_non_contiguous_h1_history,
        test_donchian48_ablation_is_opt_in_and_freezes_exact_three_arms,
        test_paired_donchian48_comparison_requires_three_exact_arms,
        test_paired_donchian48_rejects_missing_shared_invariant,
        test_paired_donchian48_rejects_missing_or_invalid_arm_metadata,
        test_donchian_arms_use_their_own_volume_lookback,
        test_volume_lookback_is_resolved_per_registered_donchian_arm,
        test_paired_donchian48_rejects_changed_volume_lookback,
        test_three_arm_donchian48_manifest_pairs_ema_only_within_d48,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} tests passed")
