# Bybit collector static audit — 2026-11-25

## Scope and source revision

Read-only inspection of the existing Bybit acquisition code on:

- Source branch: `research/market-regime-v1-main`
- Source commit: `7e5f6259bf2b02b81a69168859b795610095184f`
- No workflow was dispatched, no API request was made by this audit, no data was downloaded, and no PnL/backtest was run.
- This report is stored on the isolated diagnostic branch `research/bybit-public-api-smoke-test`; the main research branch and `main` were not modified.

## Executive conclusion

**A Bybit historical collector already exists. Do not write a second downloader.** The repository contains working-shaped collection code and workflows for the core public datasets, but it does not contain a captured Bybit archive or dated Bybit snapshots in the inspected research branch. The user's three successful browser smoke tests establish endpoint reachability only; they do not establish historical coverage or acceptance of a research dataset.

## Existing components

| Component | Existing implementation | Static finding |
|---|---|---|
| Trade OHLCV | `scripts/archive_bybit_market_history.py`, `GET /v5/market/kline` | H1 collection, chunked requests, UTC alignment, OHLC validation and exact expected timestamp-grid check |
| Mark Price | Same collector, `GET /v5/market/mark-price-kline` | H1 collection, OHLC validation and exact grid check; supports the terminal settlement candle when required |
| Funding | Same collector, `GET /v5/market/funding/history` | Bounded windows, recursive subdivision when a 200-row response saturates, duplicate rejection and query-page metadata |
| Instrument specifications | `scripts/snapshot_bybit_instruments.py` | Full paginated dated snapshots across documented statuses; records capture time and page observations |
| Linear universe/lifecycle | `scripts/snapshot_bybit_linear_universe.py` | Captures Trading/PendingOpen and terminal/in-progress statuses; records launch/delivery fields and page observations |
| Risk tiers | `scripts/snapshot_bybit_risk_limits.py` | Full paginated public risk-tier snapshot with structural/monotonicity checks |
| L2/trades | `scripts/probe_bybit_orderbook_archives.py`, `scripts/inspect_bybit_orderbook_sample.py`, `scripts/inspect_bybit_trade_sample.py`, `scripts/bybit_l2_queue_replay.py` | Probe/sample/replay tooling exists; this is not proof of a complete historical L2/trade archive |
| Fee history | No accepted dated public fee-history collector/archive identified | D8 remains open; do not substitute a current fee quote for historical fee terms |

Relevant workflows already exist:

- `.github/workflows/bybit-market-history-archive.yml`
- `.github/workflows/bybit-instrument-snapshots.yml`
- `.github/workflows/bybit-linear-universe-history.yml`
- `.github/workflows/bybit-risk-limit-snapshots.yml`

The market-history workflow defaults to a self-hosted runner and has an optional GitHub-hosted runner choice. The other three snapshot workflows are self-hosted only. They contain a country check that refuses US/Mainland China egress. The market workflow also requires a dated universe snapshot and dated instrument snapshots before collection.

## Important implementation and evidence gaps

### 1. No Bybit archive is present in the inspected branch

The recursive Git tree contains six CryptoFetch ZIPs under `data/archives/cryptofetch/`. It contains no files under `data/archives/bybit/`, `data/universe_history/linear/`, `data/instrument_specs/linear/`, or `data/instrument_specs/risk_limits/`.

This is an observation about the inspected Git tree, not a claim that no artifact exists anywhere outside the branch.

### 2. Collector does not preserve raw HTTP response bodies

The active collector's `_request_json()` parses the response and returns only the `result` object. It does not save the original HTTP response envelope/body, response headers, or a per-response raw-body SHA-256.

Funding has a sidecar with normalized CSV hash, row count and request-page coverage metadata. Trade OHLCV and Mark Price are written as normalized CSVs and checked for exact timestamp coverage, but their individual request/response pages are not preserved as raw evidence.

Dated instrument/universe/risk snapshots retain response row objects in JSON with collection timestamps/page observations, but not the original raw HTTP envelope bytes.

**Consequence:** the current collector can create useful normalized research archives, but its provenance is weaker than a raw-response archive with immutable page-level hashes. This should be reviewed before accepting a Bybit archive as canonical evidence.

### 3. Funding schedule remains conditional on snapshot observations

The collector requires dated instruments-info snapshots and constructs an expected settlement schedule from their `fundingInterval` values. Existing audits correctly identify the residual limitation: point-in-time observations do not prove the interval did not change and revert between snapshots, and fetch time is not an exact effective-time boundary.

The current Bybit endpoint documentation does not provide a complete historical effective-time journal for those changes. Therefore Funding schedule validation is conditional evidence, not a complete historical guarantee.

### 4. D4/D5/D6 are not closed by the snapshot scripts

- D4 lifecycle: the universe collector captures status observations and launch/delivery fields. A snapshot is not a complete status-transition event history; intraperiod suspension/resumption remains unproven.
- D5 instrument specifications: dated snapshots are useful observations, but do not establish exact historical effective times for every tick/lot/min-notional/filter change.
- D6 risk tiers: public snapshots preserve symbol tier tables, but do not reconstruct the account-specific applied tier or a complete historical effective-time series.

### 5. D7/D8 remain outside the current accepted package

The L2/trade scripts are probes or sample inspectors and do not demonstrate a continuous, complete order-book/trade history suitable for capacity/queue claims. No accepted dated historical fee schedule was found. Do not claim maker fill realism, queue position, capacity or historical fees from these tools.

### 6. Legacy downloader contains unsafe network advice

The legacy root-level `bybit_downloader.py` error message for HTTP 403 suggests changing network/VPN or using another regional hostname. That wording is inconsistent with this project's no-circumvention rule. Do not follow the VPN suggestion. The active archive collector instead validates an allowlist of official HTTPS Bybit API hosts and the workflows check runner egress geography.

This is a documentation/code-message issue; no code was changed in this audit.

## Gate summary

| Gate / need | Existing code | Evidence status |
|---|---|---|
| D1 trade OHLCV | Collector and strict H1 grid check | Implementation exists; no Bybit archive captured/accepted |
| D2 Mark Price | Collector and strict H1 grid check | Implementation exists; no Bybit archive captured/accepted |
| D3 Funding events/rates | Collector, page manifest and schedule validator | Implementation exists; no Bybit archive captured/accepted; historical interval effective-time trust boundary remains |
| D4 lifecycle | Dated universe snapshots | Partial observation mechanism; not complete transition history |
| D5 instrument specs | Dated instruments-info snapshots | Partial observations; no complete historical effective-time record |
| D6 risk tiers | Dated public risk-tier snapshots | Partial public tables; no account-applied historical tiers |
| D7 L2/trades | Sample/probe tools | Deferred / not accepted as complete history |
| D8 fees | No accepted dated public source found | Not accepted |

## Recommended next action

Do not create another downloader and do not dispatch the existing archive workflows yet.

First, decide whether to improve the existing collector's evidence layer in place on a dedicated research branch: save exact raw response bodies (or immutable response-page objects), request parameters, response timestamps/status/headers, per-page SHA-256, normalized-output hashes, and a manifest linking every output row range to its source page. Add offline regression tests for the manifest and tamper detection. This is a focused provenance improvement, not a new data collector.

Separately, any future real capture requires an explicitly approved and legitimately available runner/network. The successful browser tests do not authorize use of the user's phone as a collector or justify routing around any network restriction. No PnL/backtest is authorized by this audit.
