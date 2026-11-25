#!/usr/bin/env python3
"""Compare one Bybit L2 hour from Tardis and CryptoHFTData."""
import csv, gzip, hashlib, json, sys, tempfile, urllib.request
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

DATE, HOUR, SYMBOL = "2026-11-01", "12", "BTCUSDT"
TARDIS_URL = "https://datasets.tardis.dev/v1/bybit/incremental_book_L2/2026/11/01/BTCUSDT.csv.gz"
CHD_URLS = {hour: "https://api.cryptohftdata.com/download?file=" + f"bybit%2F2026-11-01%2F{hour}%2FBTCUSDT_orderbook.parquet" for hour in ("12", "13")}
START = int(datetime.fromisoformat(f"{DATE}T{HOUR}:00:00+00:00").timestamp() * 1000)
END = START + 3600000

def download(url, path, limit):
    req = urllib.request.Request(url, headers={"User-Agent": "bybit-l2-crosscheck/1.0"})
    digest, size = hashlib.sha256(), 0
    with urllib.request.urlopen(req, timeout=180) as response, path.open("wb") as out:
        if response.status != 200: raise RuntimeError(f"HTTP {response.status}")
        expected = response.headers.get("Content-Length")
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk: break
            size += len(chunk)
            if size > limit: raise RuntimeError(f"file exceeds {limit} bytes")
            out.write(chunk); digest.update(chunk)
    if expected and size != int(expected): raise RuntimeError("download size mismatch")
    return {"bytes": size, "sha256": digest.hexdigest()}

def key(ts, side, price, amount):
    if side not in ("bid", "ask"): raise ValueError(f"invalid side {side!r}")
    p, q = Decimal(str(price)), Decimal(str(amount))
    if not p.is_finite() or p <= 0 or not q.is_finite() or q < 0:
        raise ValueError("invalid price or quantity")
    return (int(ts), side, p, q)

def main():
    import pyarrow.parquet as pq
    report = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "date": DATE, "hour_utc": HOUR, "symbol": SYMBOL,
              "scope": "exact multiset comparison of L2 updates by message timestamp, side, price and absolute quantity; snapshots excluded; no PnL",
              "raw_archives_uploaded": False}
    with tempfile.TemporaryDirectory(prefix="bybit-l2-crosscheck-") as tmp:
        root = Path(tmp); tp = root / "tardis.csv.gz"
        report["tardis_download"] = download(TARDIS_URL, tp, 100*1024*1024)
        t = Counter(); snapshot_t = updates_t = 0; local_prev = None; local_regressions = 0
        with gzip.open(tp, "rt", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            expected = ["exchange","symbol","timestamp","local_timestamp","is_snapshot","side","price","amount"]
            if reader.fieldnames != expected: raise ValueError(f"Tardis schema mismatch: {reader.fieldnames}")
            for n,row in enumerate(reader,2):
                if None in row or row["exchange"] != "bybit" or row["symbol"] != SYMBOL:
                    raise ValueError(f"bad Tardis row {n}")
                local = int(row["local_timestamp"])
                if local_prev is not None and local < local_prev: local_regressions += 1
                local_prev = local
                ts = int(row["timestamp"]) // 1000
                if not START <= ts < END: continue
                if row["is_snapshot"] == "true": snapshot_t += 1; continue
                if row["is_snapshot"] != "false": raise ValueError(f"bad snapshot flag row {n}")
                t[key(ts,row["side"],row["price"],row["amount"])] += 1
                updates_t += 1
        if local_regressions: raise ValueError(f"Tardis local timestamp regressions: {local_regressions}")
        expected = ["received_time","event_time","transaction_time","symbol","event_type","first_update_id","final_update_id","prev_final_update_id","last_update_id","side","price","quantity","order_count"]
        c = Counter(); snapshot_c = updates_c = file_rows = 0
        chd_by_received_hour = {}
        for received_hour, url in CHD_URLS.items():
            cp = root / f"chd_{received_hour}.parquet"
            report[f"cryptohftdata_download_received_hour_{received_hour}"] = download(url, cp, 50*1024*1024)
            table = pq.read_table(cp)
            if table.schema.names != expected: raise ValueError("CryptoHFTData schema mismatch")
            d = table.to_pydict()
            hour_updates = 0
            receive_clock_hours = Counter()
            for i in range(len(d["event_time"])):
                if d["symbol"][i] != SYMBOL: raise ValueError(f"bad symbol row {i}")
                if d["event_type"][i] == "snapshot":
                    snapshot_c += 1
                    continue
                if d["event_type"][i] != "update": raise ValueError(f"bad event type row {i}")
                ts = int(d["event_time"][i])
                if START <= ts < END:
                    c[key(ts,d["side"][i],d["price"][i],d["quantity"][i])] += 1
                    updates_c += 1
                    hour_updates += 1
                    received_clock_hour = datetime.fromtimestamp(
                        int(d["received_time"][i]) / 1_000_000_000, tz=timezone.utc
                    ).strftime("%H")
                    receive_clock_hours[received_clock_hour] += 1
            file_rows += len(d["event_time"])
            chd_by_received_hour[received_hour] = {
                "file_rows": len(d["event_time"]),
                "selected_event_hour_update_rows": hour_updates,
                "received_clock_hour_counts_for_selected_events": dict(receive_clock_hours),
            }
        missing, extra = t-c, c-t
        matched = sum((t & c).values())
        report.update({
            "tardis_scan":{"selected_hour_update_rows":updates_t,"selected_hour_snapshot_rows":snapshot_t,"distinct_update_keys":len(t),"local_timestamp_regressions":local_regressions,"timestamp_basis":"Bybit message.ts (microseconds converted to milliseconds)"},
            "cryptohftdata_scan":{"file_rows_across_received_hours":file_rows,"selected_event_hour_update_rows":updates_c,"snapshot_rows_across_files":snapshot_c,"distinct_update_keys":len(c),"files_partitioned_by":"received_time UTC hour","by_received_hour":chd_by_received_hour,"timestamp_basis":"Bybit message.ts stored as event_time in milliseconds"},
            "comparison":{"tardis_update_rows":sum(t.values()),"cryptohftdata_update_rows":sum(c.values()),"matched_rows":matched,"missing_from_cryptohftdata":sum(missing.values()),"extra_in_cryptohftdata":sum(extra.values()),"match_pct_of_tardis":round(100*matched/max(1,sum(t.values())),6),"missing_examples":[[list(map(str,k)),v] for k,v in missing.most_common(5)],"extra_examples":[[list(map(str,k)),v] for k,v in extra.most_common(5)]}
        })
        report["comparison_status"] = "EXACT_MATCH" if not missing and not extra else "MISMATCH"
    out = Path(sys.argv[1] if len(sys.argv)>1 else "bybit_orderbook_crosscheck.json")
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    return 0 if report["comparison_status"] == "EXACT_MATCH" else 1

if __name__ == "__main__": raise SystemExit(main())
