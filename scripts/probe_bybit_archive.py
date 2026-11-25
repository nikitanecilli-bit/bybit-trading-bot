#!/usr/bin/env python3
"""Probe monthly coverage of Bybit's official public BTCUSDT H1 archive."""
import gzip
import urllib.error
import urllib.request
from pathlib import Path

samples = [
 ("2020-12","2020-12-01","2020-12-31"),
 ("2021-01","2021-01-01","2021-01-31"),
 ("2021-02","2021-02-01","2021-02-28"),
 ("2021-03","2021-03-01","2021-03-31"),
 ("2022-01","2022-01-01","2022-01-31"),
 ("2023-01","2023-01-01","2023-01-31"),
 ("2024-12","2024-12-01","2024-12-31"),
 ("2025-02","2025-02-01","2025-02-28"),
 ("2025-06","2025-06-01","2025-06-30"),
 ("2025-12","2025-12-01","2025-12-31"),
 ("2026-01","2026-01-01","2026-01-31"),
 ("2026-06","2026-06-01","2026-06-30"),
 ("2026-09","2026-09-01","2026-09-30"),
]
out=Path("bybit_archive_probe"); out.mkdir(exist_ok=True)
for label,start,end in samples:
 url=f"https://public.bybit.com/kline_for_metatrader4/BTCUSDT/{start[:4]}/BTCUSDT_60_{start}_{end}.csv.gz"
 req=urllib.request.Request(url,headers={"User-Agent":"bybit-public-history-research/1.0"})
 try:
  with urllib.request.urlopen(req,timeout=45) as response:
   data=response.read()
   decoded=gzip.decompress(data) if data[:2]==bytes([31,139]) else data
   (out/f"{label}.csv").write_bytes(decoded)
   print(label,"HTTP",response.status,"bytes",len(decoded),"rows",len(decoded.splitlines()),"first",decoded.splitlines()[0][:90] if decoded else b"")
 except urllib.error.HTTPError as e:
  print(label,"HTTP",e.code)
