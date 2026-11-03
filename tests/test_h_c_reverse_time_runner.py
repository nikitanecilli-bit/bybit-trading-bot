"""Deterministic gates for the preregistered H-C reverse-time proxy runner."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_h_c_reverse_time_robustness import (
    H1_MS, frozen_strategy_config, prepare_fold, run_reverse_time,
)
from scripts.run_h_a_relative_strength_replay import configure_engine, run_variant, em


def _rows(start_ts, end_ts, *, gap_at=None):
    rows = []
    ts = start_ts - 72 * H1_MS
    while ts <= end_ts:
        if gap_at is not None and ts == gap_at:
            rows.append(em.Candle(ts + 1, 100, 101, 99, 100, 10))
        else:
            rows.append(em.Candle(ts, 100, 101, 99, 100, 10))
        ts += H1_MS
    return rows


def test_frozen_strategy_configs_use_python_booleans_and_separate_hc_flag():
    baseline = frozen_strategy_config(False)
    candidate = frozen_strategy_config(True)
    assert baseline["maker_entry_and_tp1"] is False
    assert baseline["maker_tp1_and_target"] is False
    assert baseline["enable_post_break_invalidation"] is False
    assert candidate["enable_post_break_invalidation"] is True
    assert candidate["post_break_invalidation_bars"] == 3
    assert type(candidate["maker_entry_and_tp1"]) is bool
    assert type(candidate["maker_tp1_and_target"]) is bool


def test_prepare_fold_accepts_exact_72h_warmup_and_common_terminal_bar():
    start, end = 10_000 * H1_MS, 10_002 * H1_MS
    result = prepare_fold(
        {"BTCUSDT": _rows(start, end)}, start, end, expected_symbols=["BTCUSDT"],
    )
    assert list(result) == ["BTCUSDT"]
    assert result["BTCUSDT"][0].ts == start - 72 * H1_MS
    assert result["BTCUSDT"][-1].ts == end


def test_prepare_fold_fails_closed_for_missing_symbol_or_terminal_bar():
    start, end = 10_000 * H1_MS, 10_002 * H1_MS
    try:
        prepare_fold({}, start, end, expected_symbols=["BTCUSDT"])
    except ValueError as exc:
        assert "missing preregistered" in str(exc)
    else:
        raise AssertionError("missing frozen symbol must fail closed")

    rows = _rows(start, end - H1_MS)
    try:
        prepare_fold({"BTCUSDT": rows}, start, end, expected_symbols=["BTCUSDT"])
    except ValueError as exc:
        assert "terminal H1 candle" in str(exc)
    else:
        raise AssertionError("missing terminal bar must fail closed")


def test_prepare_fold_rejects_insufficient_warmup_and_non_contiguous_history():
    start, end = 10_000 * H1_MS, 10_002 * H1_MS
    short = _rows(start, end)[1:]
    try:
        prepare_fold({"BTCUSDT": short}, start, end, expected_symbols=["BTCUSDT"])
    except ValueError as exc:
        assert "72 H1 warmup" in str(exc)
    else:
        raise AssertionError("insufficient warmup must fail closed")

    gapped = _rows(start, end, gap_at=start)
    try:
        prepare_fold({"BTCUSDT": gapped}, start, end, expected_symbols=["BTCUSDT"])
    except ValueError as exc:
        assert "non-contiguous" in str(exc)
    else:
        raise AssertionError("non-contiguous H1 data must fail closed")


def test_hc_runner_enables_only_the_preregistered_h1_exit():
    baseline = configure_engine(["BTCUSDT"], "test-hc-baseline")
    candidate = configure_engine(
        ["BTCUSDT"], "test-hc-candidate", enable_post_break_invalidation=True,
    )
    assert baseline.cfg.enable_post_break_invalidation is False
    assert candidate.cfg.timeframe == "1h"
    assert candidate.cfg.enable_post_break_invalidation is True
    assert candidate.risk_mgr.cfg is candidate.cfg


def test_h_a_and_h_c_variants_cannot_be_combined():
    try:
        run_variant({}, 1, 2, "invalid-combined", use_h_a=True, use_h_c=True)
    except ValueError as exc:
        assert "mutually exclusive" in str(exc)
    else:
        raise AssertionError("H-A and H-C must remain separate hypotheses")


if __name__ == "__main__":
    tests = [
        test_frozen_strategy_configs_use_python_booleans_and_separate_hc_flag,
        test_prepare_fold_accepts_exact_72h_warmup_and_common_terminal_bar,
        test_prepare_fold_fails_closed_for_missing_symbol_or_terminal_bar,
        test_prepare_fold_rejects_insufficient_warmup_and_non_contiguous_history,
        test_hc_runner_enables_only_the_preregistered_h1_exit,
        test_h_a_and_h_c_variants_cannot_be_combined,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} tests passed")
