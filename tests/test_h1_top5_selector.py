"""Deterministic tests for train-only top-five candidate ranking."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.select_h1_top5_train_only import rank_candidates, common_training_bar_count, common_training_window, first_validation_timestamp, candidate_training_slice


def _row(symbol, trades, net, pf, exp, dd):
    return {
        "symbol": symbol, "trades": trades, "net_pnl": net,
        "profit_factor": pf, "expectancy_r": exp,
        "max_drawdown_pct": dd,
    }


def test_rank_uses_only_positive_net_candidates_and_deterministic_tiebreaks():
    rows = [
        _row("AAAUSDT", 50, 100, 1.4, 0.12, 10),
        _row("BBBUSDT", 40, 80, 1.5, 0.12, 8),
        _row("CCCUSDT", 80, -10, 2.0, 0.30, 4),
        _row("DDDUSDT", 29, 200, 2.0, 0.40, 2),
        _row("EEEUSDT", 60, 120, 1.0, 0.08, 15),
        _row("FFFUSDT", 60, 120, 1.6, -0.01, 5),
    ]
    evaluated, eligible = rank_candidates(rows)
    assert [row["symbol"] for row in eligible] == ["BBBUSDT", "AAAUSDT"]
    assert len(evaluated) == len(rows)
    by_symbol = {row["symbol"]: row for row in evaluated}
    assert by_symbol["CCCUSDT"]["exclusion_reasons"] == ["non_positive_net"]
    assert by_symbol["DDDUSDT"]["exclusion_reasons"] == ["insufficient_trades"]
    assert "profit_factor_not_above_1" in by_symbol["EEEUSDT"]["exclusion_reasons"]
    assert "non_positive_expectancy" in by_symbol["FFFUSDT"]["exclusion_reasons"]


def test_ties_are_resolved_by_drawdown_then_trade_count_then_symbol():
    rows = [
        _row("ZZZUSDT", 50, 100, 1.5, 0.1, 10),
        _row("BBBUSD", 60, 100, 1.5, 0.1, 10),
        _row("AAAUSDT", 50, 100, 1.5, 0.1, 8),
    ]
    _, eligible = rank_candidates(rows)
    assert [row["symbol"] for row in eligible] == ["AAAUSDT", "BBBUSD", "ZZZUSDT"]



def test_common_training_overlap_requires_every_symbol_to_share_timestamps():
    class Candle:
        def __init__(self, ts):
            self.ts = ts
    histories = {
        "AAAUSDT": [Candle(ts) for ts in range(10)],
        "BBBUSDT": [Candle(ts) for ts in range(2, 12)],
        "CCCUSDT": [Candle(ts) for ts in range(5, 15)],
    }
    assert common_training_bar_count(["AAAUSDT", "BBBUSDT"], histories) == 8
    assert common_training_bar_count(["AAAUSDT", "BBBUSDT", "CCCUSDT"], histories) == 5
    assert common_training_bar_count(["AAAUSDT", "MISSINGUSDT"], histories) == 0
    assert common_training_bar_count([], histories) == 0



def test_common_training_window_uses_exact_shared_h1_intersection():
    class Candle:
        def __init__(self, ts):
            self.ts = ts
    histories = {
        "AAAUSDT": [Candle(ts) for ts in range(0, 8 * 3_600_000, 3_600_000)],
        "BBBUSDT": [Candle(ts) for ts in range(2 * 3_600_000, 10 * 3_600_000, 3_600_000)],
        "CCCUSDT": [Candle(ts) for ts in range(3 * 3_600_000, 9 * 3_600_000, 3_600_000)],
    }
    assert common_training_window(histories) == {
        "start_timestamp_ms": 3 * 3_600_000,
        "end_timestamp_ms": 7 * 3_600_000,
        "bar_count": 5,
    }
    assert common_training_window({})["bar_count"] == 0
    assert first_validation_timestamp(histories) == 5 * 3_600_000


def test_candidate_training_slice_rejects_short_symbol_validation_leakage():
    class Candle:
        def __init__(self, ts):
            self.ts = ts

    hour = 3_600_000
    long_history = [Candle(i * hour) for i in range(10_000)]
    # Shared cutoff comes from the longest archive. This shorter archive's own
    # midpoint is much earlier, so using bars through the shared cutoff leaks.
    short_history = [Candle(i * hour) for i in range(4_000)]
    train, validation_ts, error = candidate_training_slice(
        short_history, 0, 4_998 * hour
    )
    assert train == []
    assert validation_ts == 2_000 * hour
    assert error == "candidate_training_overlaps_own_validation"

    # A candidate with the same long history remains strictly before its own
    # first validation bar, including the one-bar embargo.
    train, validation_ts, error = candidate_training_slice(
        long_history, 0, 4_998 * hour
    )
    assert error is None
    assert len(train) == 4_999
    assert train[-1].ts < validation_ts
    assert validation_ts == 5_000 * hour


def test_insufficient_positive_candidates_are_not_promoted():
    rows = [_row("AAAUSDT", 60, 100, 1.3, 0.1, 8)]
    _, eligible = rank_candidates(rows)
    assert len(eligible) == 1
    assert len(eligible[:5]) != 5


def test_non_finite_candidate_metrics_fail_closed():
    for metric in ("net_pnl", "profit_factor", "expectancy_r", "max_drawdown_pct"):
        for invalid in (float("nan"), float("inf"), float("-inf")):
            row = _row("BADUSDT", 50, 100, 1.5, 0.1, 8)
            row[metric] = invalid
            try:
                rank_candidates([row])
            except ValueError as exc:
                assert "non-finite candidate metrics" in str(exc)
                assert metric in str(exc)
            else:
                raise AssertionError(f"non-finite {metric} must fail closed: {invalid!r}")


def test_negative_candidate_trade_count_is_rejected():
    try:
        rank_candidates([_row("BADUSDT", -1, 100, 1.5, 0.1, 8)])
    except ValueError as exc:
        assert "trade count cannot be negative" in str(exc)
    else:
        raise AssertionError("negative trade count must fail closed")


if __name__ == "__main__":
    tests = [
        test_rank_uses_only_positive_net_candidates_and_deterministic_tiebreaks,
        test_ties_are_resolved_by_drawdown_then_trade_count_then_symbol,
        test_common_training_overlap_requires_every_symbol_to_share_timestamps,
        test_common_training_window_uses_exact_shared_h1_intersection,
        test_candidate_training_slice_rejects_short_symbol_validation_leakage,
        test_insufficient_positive_candidates_are_not_promoted,
        test_non_finite_candidate_metrics_fail_closed,
        test_negative_candidate_trade_count_is_rejected,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} tests passed")
