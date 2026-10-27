#!/usr/bin/env python3
"""Run isolated v15 H1 research backtests over the longest valid ZIP datasets.

Data are Binance OHLCV proxies, not Bybit execution data. This produces individual
symbol diagnostics only; it does not combine concurrent positions into a portfolio.
"""
from __future__ import annotations

import csv
import glob
import io
import os
import re
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research_v15.backtest import Bar, backtest_symbol
from research_v15.portfolio_replay import replay_portfolio

FILE_RE = re.compile(r"(?i)([a-z0-9]+usdt)_(1h)_.*\.csv$")
ONE_HOUR_MS = 3_600_000
MIN_BARS = 250
COMMON_START_MS = 1777420800000  # 2026-04-29T00:00:00Z
COMMON_END_MS = 1792972800000    # 2026-10-26T00:00:00Z


def load_h1_datasets():
    candidates = defaultdict(list)
    for archive in sorted(glob.glob("*.zip")):
        try:
            with zipfile.ZipFile(archive) as zf:
                for info in zf.infolist():
                    match = FILE_RE.fullmatch(os.path.basename(info.filename))
                    if not match:
                        continue
                    symbol = match.group(1).upper()
                    try:
                        with zf.open(info) as raw:
                            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
                            required = {"open_time_ms", "open", "high", "low", "close", "volume"}
                            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                                raise ValueError("missing required OHLCV columns")
                            bars = []
                            for line, row in enumerate(reader, start=2):
                                ts = int(row["open_time_ms"])
                                bar = Bar(ts, float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]), float(row["volume"]))
                                if ts <= 0 or min(bar.open, bar.high, bar.low, bar.close) <= 0 or bar.volume < 0:
                                    raise ValueError(f"invalid values at CSV line {line}")
                                if bar.high < max(bar.open, bar.close, bar.low) or bar.low > min(bar.open, bar.close, bar.high):
                                    raise ValueError(f"invalid OHLC at CSV line {line}")
                                bars.append(bar)
                        bars.sort(key=lambda b: b.ts)
                        if len(bars) < MIN_BARS:
                            continue
                        timestamps = [b.ts for b in bars]
                        if len(set(timestamps)) != len(timestamps):
                            raise ValueError("duplicate timestamps")
                        if any(b - a != ONE_HOUR_MS for a, b in zip(timestamps, timestamps[1:])):
                            raise ValueError("irregular H1 intervals")
                        if timestamps[0] > COMMON_START_MS or timestamps[-1] < COMMON_END_MS:
                            print(f"SKIP {symbol}: does not cover common test window 2026-04-29..2026-10-26")
                            continue
                        common_bars = [b for b in bars if COMMON_START_MS <= b.ts <= COMMON_END_MS]
                        if len(common_bars) != 4321:
                            print(f"SKIP {symbol}: expected 4321 common-window bars, got {len(common_bars)}")
                            continue
                        candidates[symbol].append((len(bars), archive, common_bars))
                    except Exception as exc:
                        print(f"REJECT {symbol} {archive}: {exc}")
        except zipfile.BadZipFile:
            print(f"REJECT invalid ZIP: {archive}")
    chosen = {}
    for symbol, options in candidates.items():
        options.sort(key=lambda x: (x[0], x[1]), reverse=True)
        chosen[symbol] = options[0]
        if len(options) > 1:
            print(f"DUPLICATE {symbol}: using longest source from {options[0][1]} ({options[0][0]} source bars; {len(options[0][2])} common-window bars)")
    return chosen


def main():
    datasets = load_h1_datasets()
    if not datasets:
        raise SystemExit("No valid H1 datasets found in ZIP archives in current directory.")
    results = []
    for symbol, (count, archive, bars) in sorted(datasets.items()):
        result = backtest_symbol(bars, symbol=symbol)
        result["source_archive"] = archive
        result["start_utc"] = datetime.fromtimestamp(bars[0].ts / 1000, tz=timezone.utc).isoformat()
        result["end_utc"] = datetime.fromtimestamp(bars[-1].ts / 1000, tz=timezone.utc).isoformat()
        results.append(result)
        print(f"{symbol}: trades={result['trades_count']}, net={result['net_pnl']:.2f} USDT, PF={result['profit_factor']}, DD={result['max_dd_pct']:.2f}%")

    print("COMMON WINDOW: 2026-04-29T00:00Z through 2026-10-26T00:00Z (4321 H1 bars per symbol)")
    print("\nSUMMARY — independent per-symbol runs, not a portfolio")
    print("symbol,bars,start_utc,end_utc,trades,net_pnl,gross_pnl,costs_including_slippage,profit_factor,expectancy_r,max_dd_pct,source_archive")
    for r in results:
        print(",".join(str(r[k]) for k in ("symbol", "bars", "start_utc", "end_utc", "trades_count", "net_pnl", "gross_pnl", "costs_including_slippage", "profit_factor", "expectancy_r", "max_dd_pct", "source_archive")))
    net_positive = sum(r["net_pnl"] > 0 for r in results)
    total_trades = sum(r["trades_count"] for r in results)
    print(f"SUMMARY symbols={len(results)} profitable_symbols={net_positive} total_trades={total_trades} sum_individual_net_pnl={sum(r['net_pnl'] for r in results):.2f} USDT")
    print("LIMITATIONS: Binance OHLCV proxy; funding excluded; maker fill assumed on touch; conservative stop-first intrabar rule; individual symbol runs are candidate generation only; first 200 bars are indicator warm-up.")

    portfolio = replay_portfolio(results, starting_equity=10_000.0, risk_pct=0.01, max_portfolio_risk_pct=0.03)
    print("\\nPORTFOLIO REPLAY — shared equity and 3% aggregate stop-risk cap")
    print(f"starting_equity={portfolio['starting_equity']:.2f} ending_equity={portfolio['ending_equity']:.2f} net_pnl={portfolio['net_pnl']:.2f} USDT")
    print(f"candidate_trades={portfolio['candidate_trades']} accepted={portfolio['accepted_trades']} rejected={portfolio['rejected_trades']} acceptance={portfolio['acceptance_rate_pct']:.2f}%")
    print(f"max_realized_drawdown={portfolio['max_realized_drawdown_pct']:.2f}% reconciliation_error={portfolio['reconciliation_error']:.10f}")
    print(f"accepted_gross_pnl={portfolio['accepted_gross_pnl']:.2f} fees={portfolio['accepted_fees']:.2f} slippage={portfolio['accepted_slippage']:.2f} USDT")
    print("\nPORTFOLIO SYMBOL DIAGNOSTICS — ranked by accepted-trade net PnL")
    print("symbol,candidates,accepted,rejected,acceptance_pct,candidate_net_pnl,accepted_net_pnl")
    ranked = sorted(portfolio["by_symbol"], key=lambda item: item["accepted_net_pnl"])
    for item in ranked:
        print(f"{item['symbol']},{item['candidate_trades']},{item['accepted_trades']},{item['rejected_trades']},{item['acceptance_rate_pct']:.2f},{item['candidate_net_pnl']:.2f},{item['accepted_net_pnl']:.2f}")
    print("PORTFOLIO REPLAY LIMITATIONS: candidate signals come from independent per-symbol runs; rejected entries do not regenerate later signals; drawdown is realized-only; funding, correlation, gap risk and portfolio mark-to-market are excluded.")


if __name__ == "__main__":
    main()
