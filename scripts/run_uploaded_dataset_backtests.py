#!/usr/bin/env python3
"""Reproducible per-symbol backtests over uploaded CryptoFetch Binance OHLCV ZIPs.

These are per-symbol diagnostic runs, not a combined portfolio test. The CSVs
are Binance OHLCV, so they are a market-data proxy for the Bybit execution model.
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
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import Bybit_Trading_Engine_v14_research as engine_mod


FILE_RE = re.compile(r"(?i)([a-z0-9]+usdt)_(1h|15m)_.*\.csv$")
TIMEFRAME_MS = {"15m": 900_000, "1h": 3_600_000}
MIN_BARS = 200


def read_zip_datasets() -> Dict[Tuple[str, str], tuple]:
    """Pick the longest valid file for each symbol/timeframe across ZIP archives."""
    candidates = defaultdict(list)
    for archive in sorted(glob.glob("*.zip")):
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                match = FILE_RE.fullmatch(os.path.basename(info.filename))
                if not match:
                    continue
                symbol, timeframe = match.group(1).upper(), match.group(2).lower()
                try:
                    with zf.open(info) as raw:
                        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                        reader = csv.DictReader(text)
                        required = {"open_time_ms", "open", "high", "low", "close", "volume"}
                        if not reader.fieldnames or not required.issubset(reader.fieldnames):
                            raise ValueError(f"missing columns: {required}")
                        rows = []
                        for line, row in enumerate(reader, start=2):
                            ts = int(row["open_time_ms"])
                            o, h, l, c, v = (float(row[k]) for k in ("open", "high", "low", "close", "volume"))
                            if ts <= 0 or min(o, h, l, c) <= 0 or v < 0:
                                raise ValueError(f"invalid values at line {line}")
                            if h < max(o, c, l) or l > min(o, c, h):
                                raise ValueError(f"invalid OHLC at line {line}")
                            rows.append(engine_mod.Candle(ts, o, h, l, c, v))
                    rows.sort(key=lambda c: c.ts)
                    if len(rows) < MIN_BARS:
                        print(f"SKIP {symbol} {timeframe}: only {len(rows)} bars ({archive})")
                        continue
                    timestamps = [c.ts for c in rows]
                    if len(set(timestamps)) != len(timestamps):
                        raise ValueError("duplicate timestamps")
                    step = TIMEFRAME_MS[timeframe]
                    deltas = [b - a for a, b in zip(timestamps, timestamps[1:])]
                    if any(delta != step for delta in deltas):
                        raise ValueError(f"irregular intervals; distinct deltas={sorted(set(deltas))[:8]}")
                    candidates[(symbol, timeframe)].append((len(rows), archive, rows))
                except Exception as exc:
                    print(f"REJECT {symbol} {timeframe} from {archive}: {exc}")
    chosen = {}
    for key, options in candidates.items():
        options.sort(key=lambda item: (item[0], item[1]), reverse=True)
        chosen[key] = options[0]
        if len(options) > 1:
            print(f"DUPLICATE {key[0]} {key[1]}: using {options[0][1]} ({options[0][0]} bars)")
    return chosen


def run() -> None:
    datasets = read_zip_datasets()
    if not datasets:
        raise SystemExit("No valid OHLCV datasets found in uploaded ZIP archives.")

    rows_out = []
    for (symbol, timeframe), (bar_count, archive, candles) in sorted(datasets.items()):
        engine = engine_mod.UnifiedQuantEngine(journal_output_path="/tmp/ignored_dataset_audit_journal.json")
        cfg = engine.cfg
        cfg.bot_version = "uploaded-data-audit"
        cfg.timeframe = timeframe
        cfg.active_trading_pool = [symbol]
        cfg.capital_usdt = 10_000.0
        cfg.max_risk_trade_pct = 1.0
        cfg.max_portfolio_risk_pct = 2.0
        cfg.max_concurrent_positions = 1
        cfg.daily_stop_loss_pct = 5.0
        cfg.emergency_kill_switch_pct = 30.0
        cfg.donchian_period = 20
        cfg.atr_period = 14
        cfg.min_volume_ratio = 1.6
        cfg.stop_atr_mult = 2.5
        cfg.tp1_r_multiple = 2.0
        cfg.tp2_r_multiple = 5.0
        cfg.atr_trail_mult = 3.0
        cfg.max_hold_bars = 32
        cfg.maker_entry_and_tp1 = False
        cfg.enable_h2_range_fade = False
        cfg.validate()
        engine.risk_mgr.cfg = cfg
        engine.tg.send_message = lambda *_args, **_kwargs: None
        candles_by_symbol = {symbol: candles}
        engine_mod.check_alignment(candles_by_symbol)
        audit = engine_mod.run_simulation_pass(
            engine, candles_by_symbol, [symbol],
            data_label=f"BINANCE_PROXY {timeframe} {symbol}",
        )
        trades = engine.closed_trades
        costs = sum(t.exchange_fees_usdt + t.slippage_cost_usdt for t in trades)
        start = candles[0].ts
        end = candles[-1].ts
        rows_out.append({
            "timeframe": timeframe,
            "symbol": symbol,
            "bars": bar_count,
            "start_utc": engine_mod.datetime.fromtimestamp(start / 1000, tz=engine_mod.timezone.utc).isoformat(),
            "end_utc": engine_mod.datetime.fromtimestamp(end / 1000, tz=engine_mod.timezone.utc).isoformat(),
            "trades": audit["total_trades"],
            "gross_pnl_usdt": round(sum(t.gross_pnl for t in trades), 2),
            "costs_usdt": round(costs, 2),
            "net_pnl_usdt": round(audit["net_pnl"], 2),
            "net_pf": round(audit["pf"], 4),
            "expectancy_r": round(audit["expectancy_r"], 4),
            "max_dd_pct": round(audit["max_dd_pct"], 2),
            "source_archive": archive,
        })

    print("\nRESULTS: individual-symbol runs; each starts at 10,000 USDT, 1% risk/trade.")
    print("Source files are Binance OHLCV, used as a market-data proxy; fees/slippage are modelled.")
    print("timeframe,symbol,bars,start_utc,end_utc,trades,gross_pnl_usdt,costs_usdt,net_pnl_usdt,net_pf,expectancy_r,max_dd_pct")
    for r in rows_out:
        print(",".join(str(r[k]) for k in (
            "timeframe", "symbol", "bars", "start_utc", "end_utc", "trades",
            "gross_pnl_usdt", "costs_usdt", "net_pnl_usdt", "net_pf",
            "expectancy_r", "max_dd_pct"
        )))
    for timeframe in ("15m", "1h"):
        group = [r for r in rows_out if r["timeframe"] == timeframe]
        if not group:
            continue
        print(
            f"SUMMARY {timeframe}: symbols={len(group)}, trades={sum(r['trades'] for r in group)}, "
            f"net_pnl_sum={sum(r['net_pnl_usdt'] for r in group):.2f} USDT, "
            f"profitable_symbols={sum(r['net_pnl_usdt'] > 0 for r in group)}, "
            f"median_symbol_pf={sorted(r['net_pf'] for r in group)[len(group)//2]:.4f}"
        )


if __name__ == "__main__":
    run()
