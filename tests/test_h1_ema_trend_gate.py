"""Deterministic tests for opt-in full-history EMA50/200 H1 gating."""
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_h1_shared_capital_portfolio_validation import (
    build_ema50_200_label_maps, h1_variant_modes, h1_variant_name,
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
        test_ema50_200_gate_is_explicitly_opt_in_and_rejects_invalid_values,
        test_ema_gate_precomputes_full_history_and_uses_exact_scored_timestamp,
        test_ema_gate_fails_closed_without_1000_pre_roll_bars,
        test_ema_gate_fails_closed_for_missing_symbol_or_history,
        test_ema_gate_rejects_non_contiguous_h1_history,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} tests passed")
