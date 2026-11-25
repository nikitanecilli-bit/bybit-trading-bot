#!/usr/bin/env python3
"""Diagnose one historical CryptoHFTData Bybit trade object without retaining it."""
import hashlib, json, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path
import pyarrow.parquet as pq

FILE="bybit/2025-07-01/00/BTCUSDT_trades.parquet"
BASES=("https://api.cryptohftdata.com/download","https://api.cryptohftdata.com/v1/download")
def inspect(base):
    url=base+"?"+urllib.parse.urlencode({"file":FILE})
    req=urllib.request.Request(url,headers={"User-Agent":"cryptohftdata-historical-file-probe/1.0"})
    digest=hashlib.sha256(); size=0; prefix=b""; tail=b""
    try:
        with urllib.request.urlopen(req,timeout=60) as response:
            status=response.status; headers=dict(response.headers.items()); final_url=response.geturl()
            while True:
                chunk=response.read(1024*1024)
                if not chunk: break
                if len(prefix)<64: prefix=(prefix+chunk)[:64]
                tail=(tail+chunk)[-8:]
                size+=len(chunk)
                if size>20*1024*1024: raise RuntimeError("exceeded 20 MiB safety limit")
                digest.update(chunk)
        result={"url":url,"final_url":final_url,"status":status,
                "content_type":headers.get("Content-Type"),"content_length":headers.get("Content-Length"),
                "bytes":size,"sha256":digest.hexdigest(),"prefix_hex":prefix.hex(),
                "prefix_text":prefix[:64].decode("utf-8",errors="replace"),
                "tail_hex":tail.hex(),"parquet_magic_ok":prefix[:4]==b"PAR1" and tail==b"PAR1"}
        return result
    except urllib.error.HTTPError as exc:
        body=exc.read(1024)
        return {"url":url,"status":exc.code,"content_type":exc.headers.get("Content-Type"),
                "error":str(exc),"body_preview":body.decode("utf-8",errors="replace")}
    except Exception as exc:
        return {"url":url,"error":f"{type(exc).__name__}: {exc}","bytes_read":size}
def main():
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"file":FILE,
            "scope":"single historical object response diagnostic; no strategy data or PnL",
            "results":[inspect(base) for base in BASES]}
    print(json.dumps(report,indent=2))
    Path("/tmp/cryptohftdata_historical_probe.json").write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__": main()
