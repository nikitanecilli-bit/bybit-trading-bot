# Bybit raw-response semantic audit — 2026-11-25

## Purpose

Add an offline validator that independently re-opens the raw Bybit V5 response bodies and checks whether each D1-D3 collection-page description agrees with the actual response content.

## Implemented

- Added `scripts/validate_bybit_raw_semantics.py`.
- Added `tests/test_validate_bybit_raw_semantics.py`.
- Extended `.github/workflows/bybit-raw-response-evidence-tests.yml` to compile and run the new validator tests.
- The validator checks stream-to-endpoint mapping, GET identity, symbol/category, API envelope return code, actual row count, timestamp parseability, duplicate timestamps within a page, first/last timestamp claims, requested page time bounds, response hash linkage, duplicate references and unreferenced records.
- The validator is offline: it reads only the archive manifest and local raw response bodies. It makes no network requests.

## Deliberate limits

This is a semantic page-inventory check, not final data acceptance:
- It does not prove that the API supplied all historical records.
- It does not validate every OHLC relationship or funding interval schedule.
- It does not yet independently reconstruct normalized CSV rows and compare every value against the union of raw pages.
- It does not establish lifecycle, historical contract specifications, risk tiers, fees, or L2/trade history.
- A clean result cannot by itself ACCEPT D1-D3.

## Tests and status

Two offline tests cover a valid three-stream manifest and deliberate tampering of row counts, endpoint/page references, and timestamp bounds.

The workflow definition now includes these tests. A workflow run for the latest commit has not yet been observed; therefore no CI success is claimed for this addition.

No exchange API calls, data collection, archive generation, PnL, backtest, parameter sweep, or event study were performed.

## Repository safety

Changes remain on `research/bybit-raw-response-evidence-v1`, within draft PR #17 targeting `research/market-regime-v1-main`. No merge was performed and `main` was not changed.
