#!/usr/bin/env python3
"""Probe official Bybit public archive month files; no credentials."""
import gzip
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

samples = [
    ("2020-01", "2020-01-01", "2020-01-31"),
    ("2021-06", "2021-06-01", "2021-06-30"),
    ("2024-01", "2024-01-01", "2024-01-31"),
    ("2025-01", "2025-01-01", "2025-01-31"),
    ("2026-10", "2026-10-01", "2026-10-31"),
]
out = Path("bybit_archive_probe")
out.mkdir(exist_ok=True)
for label, start, end in samples:
    url = f"https://public.bybit.com/kline_for_metatrader4/BTCUSDT/{start[:4]}/BTCUSDT_60_{start}_{end}.csv.gz"
    req = urllib.request.Request(url, headers={"User-Agent":"bybit-public-history-research/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            data = response.read()
            decoded = gzip.decompress(data) if data[:2] == bytes([31,139]) else data
            (out / f"{label}.csv").write_bytes(decoded)
            print(label, "HTTP", response.status, "bytes", len(data), "rows", len(decoded.splitlines()), "first", decoded.splitlines()[0][:100] if decoded else "")
    except urllib.error.HTTPError as e:
        print(label, "HTTP", e.code)
