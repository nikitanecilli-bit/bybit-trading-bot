# Bybit snapshot raw-response evidence — implementation report (2026-11-25)

## Status

**Implemented and validated with offline GitHub Actions tests. Draft PR only; not merged. No exchange data was collected.**

- Branch: `research/bybit-raw-response-evidence-v1`
- Draft PR: https://github.com/nikitanecilli-bit/bybit-trading-bot/pull/17
- Base: `research/market-regime-v1-main` (not `main`)
- Shared evidence helper: `scripts/bybit_raw_evidence.py`

## Coverage added

The evidence layer now covers the three dated Bybit snapshot collectors:

1. `scripts/snapshot_bybit_instruments.py` — paginated instrument-info snapshots by documented status filters.
2. `scripts/snapshot_bybit_linear_universe.py` — linear universe lifecycle observations across Trading/PendingOpen and terminal/prelaunch status queries.
3. `scripts/snapshot_bybit_risk_limits.py` — paginated public risk-limit tier snapshots.

For each successful public GET response, the collector preserves:

- Exact response body bytes in a content-addressed file.
- SHA-256 and byte length of the body.
- HTTP status and selected response headers.
- Exact method, official API base URL, endpoint, and query parameters.
- Retrieval timestamp in UTC.
- A separate audit JSON record.

Each collection-page entry in the evidence manifest links to its raw response request ID and body hash. The manifest also records the normalized snapshot's relative path, byte count, and SHA-256.

The shared validator checks raw body hashes and sizes, audit-record equality, unique request IDs, one-to-one collection-page-to-response coverage, page-index/status consistency with the normalized snapshot, and normalized snapshot hash/size. It rejects orphaned raw responses, missing page links, duplicate references, and mismatched page inventories. Dated snapshot paths are protected against accidental overwrite. Each capture uses a unique working directory, so an interrupted collection cannot silently mix into the next run.

## Validation

GitHub Actions run:

https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45581283920

**Result: SUCCESS** (latest strengthened validator, commit `32a1f6a11a2ec1d40653f3d08242ca8b24635bf1`)

- Python compilation: PASS
- Raw evidence capture/finalization, body and normalized-output tamper tests: PASS
- Missing page link, orphan response, duplicate reference and page-inventory rejection tests: PASS
- Instrument snapshot regression tests: PASS
- Linear universe snapshot regression tests: PASS
- Risk-limit snapshot regression tests: PASS
- Existing market-history collector regression tests: PASS

The workflow uses synthetic fixtures and GitHub-hosted runners. It does not call Bybit or collect market data.

## Boundaries and unresolved issues

- These are dated point-in-time observations, not a complete historical record of every instrument status or specification change.
- A successful snapshot cannot prove there were no unobserved intraday suspend/resume transitions.
- Public risk-limit tiers are not the same as an account's historical applied risk tier.
- Historical tick/lot/minimum-order filters and their effective-time history remain incomplete.
- No L2/trade archive or dated fee history was established by this work.
- Hashes establish file integrity relative to the manifest; they are not an external signature or trusted timestamp authority.
- No data gate was promoted to ACCEPTED solely because the collector implementation now has stronger provenance.
- No historical data collection, PnL, backtest, parameter sweep, or event study was run.

## Next step

Review draft PR #17 and its checks. If accepted, merge only into `research/market-regime-v1-main` after explicit review. Historical data capture remains a separate operation and should be explicitly authorized and run only on an allowed runner/network.
