#!/usr/bin/env python3
"""Run the research engine separately for every symbol and export an all-symbol report.

This is intentionally a serial wrapper around the existing engine; it does not alter
strategy rules or claim funding-adjusted results. Each run receives only one symbol's
CSV so portfolio-level metrics cannot hide weak instruments.
"""
import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbols", nargs="+", required=True)
    p.add_argument("--data-dir", type=Path, required=True, help="aligned engine CSV files")
    p.add_argument("--engine", type=Path, default=Path("Bybit_Trading_Engine_v14_research.py"))
    p.add_argument("--config", type=Path, help="optional research config JSON")
    p.add_argument("--out-dir", type=Path, default=Path("per_symbol_results"))
    p.add_argument("--python", default=sys.executable)
    args = p.parse_args()

    engine = args.engine.resolve()
    data_dir = args.data_dir.resolve()
    config = args.config.resolve() if args.config else None
    if not engine.is_file():
        p.error(f"engine not found: {engine}")
    if config and not config.is_file():
        p.error(f"config not found: {config}")

    symbols = list(dict.fromkeys(s.upper() for s in args.symbols))
    if not symbols:
        p.error("provide at least one symbol")
    for symbol in symbols:
        source = data_dir / f"{symbol}.csv"
        if not source.is_file():
            p.error(f"missing input CSV: {source}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    failures = []
    with tempfile.TemporaryDirectory(prefix="bybit-symbol-tests-") as tmp:
        tmp_root = Path(tmp)
        for index, symbol in enumerate(symbols, start=1):
            isolated_data = tmp_root / symbol
            isolated_data.mkdir()
            shutil.copy2(data_dir / f"{symbol}.csv", isolated_data / f"{symbol}.csv")
            journal = (args.out_dir / f"{symbol}_journal.json").resolve()
            cmd = [args.python, str(engine), "--mode", "backtest",
                   "--data-dir", str(isolated_data), "--journal", str(journal)]
            if config:
                cmd += ["--config", str(config)]
            print(f"[{index}/{len(symbols)}] Running {symbol}...", flush=True)
            proc = subprocess.run(cmd, text=True, capture_output=True)
            (args.out_dir / f"{symbol}_stdout.log").write_text(proc.stdout, encoding="utf-8")
            (args.out_dir / f"{symbol}_stderr.log").write_text(proc.stderr, encoding="utf-8")
            if proc.returncode != 0 or not journal.is_file():
                failures.append({"symbol": symbol, "return_code": proc.returncode,
                                 "error": (proc.stderr or proc.stdout)[-2000:]})
                print(f"  FAILED (see {symbol}_stderr.log)", flush=True)
                continue
            try:
                payload = json.loads(journal.read_text(encoding="utf-8"))
                summary = payload.get("summary", {})
                row = {"symbol": symbol, **summary, "journal_file": journal.name}
                records.append(row)
                print(f"  OK; summary keys: {', '.join(summary.keys())}", flush=True)
            except (OSError, json.JSONDecodeError) as exc:
                failures.append({"symbol": symbol, "error": f"could not parse journal: {exc}"})

    # Preserve every summary key, even if different engine versions return different fields.
    fields = ["symbol"] + sorted({key for row in records for key in row if key != "symbol"})
    with (args.out_dir / "per_symbol_summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    (args.out_dir / "failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out_dir / "per_symbol_summary.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Completed: {len(records)} succeeded, {len(failures)} failed.")
    print(f"Report: {args.out_dir / 'per_symbol_summary.csv'}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
