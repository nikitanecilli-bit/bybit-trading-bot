"""Deterministic tests for opt-in full-history EMA50/200 H1 gating."""
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_h1_shared_capital_portfolio_validation import (
    LEVERAGE_MODE, LEVERAGE_VAL, build_ema50_200_label_maps,\n    build_paired_ema_comparison, h1_variant_modes, h1_variant_name,
    resolve_ema50_200_gate,
)
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


if __name__ == "__main__":
    tests = [
        test_ema50_200_gate_is_explicitly_opt_in_and_rejects_invalid_values,
        test_paired_ema_comparison_matches_identical_configs_and_costs,
        test_paired_ema_comparison_fails_closed_for_unpaired_rows,
        test_ema_gate_precomputes_full_history_and_uses_exact_scored_timestamp,
        test_ema_gate_fails_closed_without_1000_pre_roll_bars,
        test_ema_gate_fails_closed_for_missing_symbol_or_history,
        test_ema_gate_rejects_non_contiguous_h1_history,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} tests passed")
