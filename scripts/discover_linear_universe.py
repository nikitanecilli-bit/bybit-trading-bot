#!/usr/bin/env python3
"""Discover current tradable Bybit USDT perpetuals and optionally rank by 24h turnover.

This is a current-universe snapshot only. It does NOT reconstruct historical listings,
delistings, or past liquidity, so results using it remain vulnerable to survivorship bias.
"""
import argparse
import json
import time
from pathlib import Path

import requests

BASE = "https://api.bybit.com"
TIMEOUT = 20


def get_json(session, path, params):
    response = session.get(BASE + path, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if payload.get("retCode") != 0:
        raise RuntimeError(f"Bybit API error {payload.get('retCode')}: {payload.get('retMsg')}")
    return payload.get("result") or {}


def list_linear_usdt_perpetuals(session):
    cursor = None
    symbols = []
    seen_cursors = set()
    while True:
        params = {"category": "linear", "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        result = get_json(session, "/v5/market/instruments-info", params)
        for item in result.get("list", []):
            if (item.get("status") == "Trading" and item.get("quoteCoin") == "USDT"
                    and item.get("settleCoin") == "USDT" and item.get("contractType") == "LinearPerpetual"):
                symbols.append(item["symbol"])
        next_cursor = result.get("nextPageCursor") or ""
        if not next_cursor:
            break
        if next_cursor in seen_cursors:
            raise RuntimeError("Bybit returned a repeated pagination cursor")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
        time.sleep(0.1)
    return sorted(set(symbols))


def ticker_turnover(session):
    result = get_json(session, "/v5/market/tickers", {"category": "linear"})
    ranked = {}
    for item in result.get("list", []):
        try:
            ranked[item["symbol"]] = float(item.get("turnover24h") or 0)
        except (TypeError, ValueError):
            ranked[item.get("symbol", "")] = 0.0
    return ranked


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--top", type=int, default=0,
                   help="keep top N tradable USDT perpetuals by current 24h turnover; 0 means all")
    p.add_argument("--min-turnover-usdt", type=float, default=0.0,
                   help="minimum current 24h turnover; 0 disables the filter")
    p.add_argument("--out", type=Path, default=Path("universe_symbols.txt"))
    p.add_argument("--json-out", type=Path, default=Path("universe_snapshot.json"))
    args = p.parse_args()
    if args.top < 0 or args.min_turnover_usdt < 0:
        p.error("--top and --min-turnover-usdt must be non-negative")

    with requests.Session() as session:
        symbols = list_linear_usdt_perpetuals(session)
        turnover = ticker_turnover(session)
    rows = [{"symbol": s, "turnover24h_usdt": turnover.get(s, 0.0)} for s in symbols]
    rows = [r for r in rows if r["turnover24h_usdt"] >= args.min_turnover_usdt]
    rows.sort(key=lambda r: (-r["turnover24h_usdt"], r["symbol"]))
    if args.top:
        rows = rows[:args.top]

    args.out.write_text("\n".join(r["symbol"] for r in rows) + ("\n" if rows else ""), encoding="utf-8")
    args.json_out.write_text(json.dumps({
        "source": "Bybit V5 public market endpoints",
        "universe_type": "current tradable USDT linear perpetuals",
        "ranking": "current 24h turnover descending",
        "warning": "Current snapshot only; historical survivorship bias is not corrected.",
        "count": len(rows),
        "symbols": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} symbols to {args.out} and snapshot to {args.json_out}")
    print("Universe snapshot is current, not historical; do not treat it as survivorship-bias-free.")


if __name__ == "__main__":
    main()
