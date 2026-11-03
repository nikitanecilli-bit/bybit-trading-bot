"""Deterministic tests for train-only top-five candidate ranking."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.select_h1_top5_train_only import rank_candidates


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
        _row("EEEUSDT", 60, 120, 1.1, 0.08, 15),
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


def test_insufficient_positive_candidates_are_not_promoted():
    rows = [_row("AAAUSDT", 60, 100, 1.3, 0.1, 8)]
    _, eligible = rank_candidates(rows)
    assert len(eligible) == 1
    assert len(eligible[:5]) != 5


if __name__ == "__main__":
    tests = [
        test_rank_uses_only_positive_net_candidates_and_deterministic_tiebreaks,
        test_ties_are_resolved_by_drawdown_then_trade_count_then_symbol,
        test_insufficient_positive_candidates_are_not_promoted,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)}/{len(tests)} tests passed")
