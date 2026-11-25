# Bybit BTCUSDT historical L2 archive validation

Date: 2026-11-25  
Branch: research/h1-volume-lookback-provenance-fix

## Result

The public Bybit Historical Data OrderBook archive was downloaded and parsed successfully for two sample dates spanning both published depth formats.

| Date | Depth | ZIP size | Records | Snapshots | Deltas |
|---|---:|---:|---:|---:|---:|
| 2024-04-11 | 500 levels/side | 238.3 MB | 863,905 | 2 | 863,903 |
| 2025-11-02 | 200 levels/side | 127.1 MB | 861,804 | 2 | 861,802 |

Both archives:
- passed ZIP CRC validation;
- contained one JSONL data member;
- had zero malformed JSON records;
- had zero symbol/topic mismatches;
- had no non-increasing update IDs or sequence values;
- reached the expected maximum snapshot depth (500 or 200 levels per side).

## Record structure

Top-level keys: cts, data, topic, ts, type.  
Data keys: a, b, s, seq, u.

- type is snapshot or delta.
- snapshot contains the full visible bid/ask book.
- delta contains changed levels.
- each level is represented as [price, quantity].
- quantity "0" removes that price level.
- u is the per-book update ID; in both samples, delta count and u range are consistent with consecutive update IDs.
- seq is monotonic in file order.
- ts is the event timestamp in Unix milliseconds.

The archive contains two snapshots per daily file: an initial snapshot and a trailing snapshot just after the next UTC day begins. It also includes a small number of boundary deltas after midnight (39 in the 2024 sample; 6 in the 2025 sample). These records must be assigned to the next UTC day or used only to validate/carry the ending book state, not counted as in-day observations for the prior day.

## Depth format

- 2024-04-11: topic orderbook.500.BTCUSDT; snapshot reached 500 bids and 500 asks.
- 2025-11-02: topic orderbook.200.BTCUSDT; snapshot reached 200 bids and 200 asks.

This is consistent with Bybit's announced change from 500 to 200 historical futures orderbook levels on 2025-08-21.

## What is not yet proven

This is archive/schema validation, not yet a full replay validation. Next we must:
1. rebuild the local book from the initial snapshot;
2. apply each delta in file order, deleting zero-quantity levels;
3. verify the second snapshot matches the reconstructed ending book within the expected boundary;
4. sample spread, depth and imbalance around known strategy signal times;
5. compare book features with public trade flow, separating RPI-marked trades when the archive exposes that flag.

No spoofing or iceberg identification is claimed from this validation alone.

## Reproduction

- Workflow: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45672403519
- Artifact ID: 15049893148
- Validator: scripts/validate_bybit_historical_orderbook_archive.py
- Source directory: https://quote-saver.bycsi.com/orderbook/linear/BTCUSDT/
