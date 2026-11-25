# Bybit raw-response semantic audit — 2026-11-25

## Purpose

Add an offline validator that independently re-opens the raw Bybit V5 response bodies and checks whether each D1-D3 collection-page description agrees with the actual response content.

## Implemented

- Added `scripts/validate_bybit_raw_semantics.py`.
- Added `tests/test_validate_bybit_raw_semantics.py`.
- Extended `.github/workflows/bybit-raw-response-evidence-tests.yml` to compile and run the new validator tests.
- The validator checks stream-to-endpoint mapping, GET identity, symbol/category, API envelope return code, actual row count, timestamp parseability, duplicate timestamps within a page, first/last timestamp claims, requested page time bounds, response hash linkage, duplicate references and unreferenced records.
- The validator is offline: it reads only the archive manifest, local raw response bodies, and normalized CSV files. It makes no network requests.
- It independently reconstructs the expected normalized Funding, OHLCV, and Mark Price rows from the raw pages, sorts them by timestamp, and compares every field and row against the corresponding CSV.
- Normalized output paths are constrained to the archive root; malformed numeric values and mismatched Funding row symbols are rejected.

## Deliberate limits

This is a semantic page-inventory check, not final data acceptance:
- It does not prove that the API supplied all historical records.
- It does not validate every OHLC relationship or funding interval schedule.
- It does not prove that the exchange API itself returned a complete or unbiased historical record; it only checks consistency between captured pages and normalized files.
- It does not establish lifecycle, historical contract specifications, risk tiers, fees, or L2/trade history.
- A clean result cannot by itself ACCEPT D1-D3.

## Tests and status

Two offline tests cover a valid three-stream manifest, deliberate tampering of row counts/page references/timestamp bounds, and alteration of a normalized CSV value while leaving the raw pages intact.

The workflow definition compiles and runs the new tests. The available GitHub run lookup did not return a run for the latest commit, so CI success for these newest changes remains unverified.

No exchange API calls, data collection, archive generation, PnL, backtest, parameter sweep, or event study were performed.

## Repository safety

Changes remain on `research/bybit-raw-response-evidence-v1`, within draft PR #17 targeting `research/market-regime-v1-main`. No merge was performed and `main` was not changed.
