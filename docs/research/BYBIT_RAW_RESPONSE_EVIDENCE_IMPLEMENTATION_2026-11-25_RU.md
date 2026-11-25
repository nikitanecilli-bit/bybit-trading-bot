# Bybit raw-response evidence layer — implementation note (2026-11-25)

## Status

**Implemented and offline-tested on an isolated branch. Not merged. No market archive was collected.**

- Branch: `research/bybit-raw-response-evidence-v1`
- Base: `research/market-regime-v1-main`
- Collector: `scripts/archive_bybit_market_history.py`
- Tests: `tests/test_archive_bybit_market_history.py`
- CI: `.github/workflows/bybit-raw-response-evidence-tests.yml`

## What changed

The existing Bybit historical collector now optionally records the exact successful HTTP response body for each public GET request used by the three core streams:

1. `/v5/market/funding/history`
2. `/v5/market/kline`
3. `/v5/market/mark-price-kline`

For each captured response it writes:

- Exact response body bytes, stored content-addressed as `bodies/<sha256>.json`.
- A separate request audit record under `requests/<request_id>.json`.
- Request method, official API base URL, endpoint, exact query parameters, retrieval timestamp, HTTP status, selected response headers, body byte length and SHA-256.
- A per-symbol `manifest.json` tying the raw response records to the collection page ranges and to the normalized Funding, trade OHLCV and Mark Price CSV outputs.
- SHA-256 hashes for the normalized output files.

Funding, trade-kline and Mark-kline page metadata now retain the raw response request ID, body hash and audit-record path. This creates a traceable link from a normalized collection page back to its exact source response.

A validator checks that each raw body exists and matches its SHA-256/byte length, audit JSON matches the record, every Funding/trade-kline/Mark page links to exactly one raw response, no response is orphaned or referenced twice, and all three normalized CSVs exist with matching SHA-256 and row counts. Paths are constrained to the raw-evidence directory or archive root as appropriate. The manifest is written only after all three streams and normalized CSVs are complete.

The collector continues to use official HTTPS Bybit API hosts and public GET endpoints only. No account/private endpoints, API keys, orders, proxies, mirrors, VPN routing or geography circumvention were added.

## Tests

GitHub Actions run:

https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45581812910

Result: **SUCCESS** (commit `c8df338b2b4605c307af02ccd92b5ccdd30a8090`)

- Python compile: PASS
- Offline Bybit collector test suite: PASS
- Raw-response capture test: PASS
- Exact body SHA-256 and byte-length verification: PASS
- Tampered-body detection: PASS
- Missing page/orphan response detection: PASS
- Normalized CSV hash and row-count verification: PASS
- Archive-flow tests verify Funding, trade-kline and Mark page records are linked one-to-one into the raw manifest: PASS

The workflow uses GitHub-hosted Ubuntu and performs no network collection. Test fixtures are synthetic.

## Important limits

- This proves the implementation and its offline tests, not that a historical Bybit archive has been collected.
- No data collection workflow was dispatched.
- No Bybit market-data archive was downloaded or committed.
- No data gate has been promoted to ACCEPTED based on this implementation alone.
- The raw-response manifest protects against accidental/tamper changes after capture, but a local hash is not an external signature or a trusted timestamp authority.
- The collector still relies on dated instrument snapshots for Funding interval reconstruction. It cannot rule out an unobserved Funding-interval change and reversion between snapshots.
- D4 lifecycle transitions, D5 exact historical specification effective times, D6 historical/account-applied risk tiers, D7 complete L2/trade history, and D8 dated fees remain unresolved or deferred.
- No PnL, backtest, sweep or event study was run or authorized.

## Next safe step

Review this isolated branch, then decide whether to merge the evidence-layer improvement into the main research branch. Only after that should a separate, explicitly approved public-data collection run be considered, using an allowed runner/network. The user-browser smoke tests do not themselves constitute a historical archive.
