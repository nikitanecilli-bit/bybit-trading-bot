#!/usr/bin/env python3
"""Probe one official Bybit public H1 archive file; no credentials."""
import gzip
import urllib.request
from pathlib import Path

url = "https://public.bybit.com/kline_for_metatrader4/BTCUSDT/2024/BTCUSDT_60_2024-01-01_2024-01-31.csv.gz"
out = Path("bybit_archive_probe")
out.mkdir(exist_ok=True)
req = urllib.request.Request(url, headers={"User-Agent":"bybit-public-history-research/1.0"})
with urllib.request.urlopen(req, timeout=45) as response:
    data = response.read()
    print("http_status:", response.status)
    print("content_type:", response.headers.get("Content-Type"))
    print("content_length:", len(data))
(out / "sample.bin").write_bytes(data)
decoded = gzip.decompress(data) if data[:2] == b"\\x1f\\x8b" else data
text = decoded[:2000].decode("utf-8", errors="replace")
(out / "sample_head.txt").write_text(text, encoding="utf-8")
print("gzip:", data[:2] == b"\\x1f\\x8b")
print("decoded_bytes:", len(decoded))
print("first_lines:")
for line in text.splitlines()[:6]:
    print(line)

# Probe run is intentionally small to verify archive reachability and file format.
