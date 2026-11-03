# Funding archive completeness audit — 2026-11-03

Branch: `research/market-regime-v1-main`
Scope: `scripts/validate_funding_coverage.py`, `scripts/run_h1_shared_capital_portfolio_validation.py`, `funding_accounting.py`, `bybit_downloader.py`, `tests/test_funding_coverage.py`
Status: **CONFIRMED P1 PREFLIGHT BLIND SPOT — DATA COMPLETENESS NOT PROVEN**
Market PnL replay: **NOT RUN**

## Finding

The current funding preflight proves consistency of records that are present; it does not prove that the funding archive contains every settlement that should exist over the scored period.

Evidence in `scripts/validate_funding_coverage.py`:

1. `_read_funding()` validates the schema, symbol, positive timestamp, finite rate and duplicate timestamps.
2. `validate_coverage()` checks that every funding timestamp present in the CSV has a matching Mark candle.
3. When trade candles are supplied, it checks exact equality of the Trade-Kline and Mark timestamp sets.
4. It reports `ok` when the funding set is non-empty and there are no funding-to-mark misses or trade/mark timestamp mismatches.

It does **not** receive an expected settlement schedule, query-window manifest, API pagination evidence, or a required funding coverage interval. It does not test gaps between settlement timestamps or whether the first/last settlement records cover the interval in which positions could be open.

The H1 runner's `validate_funding_mark_coverage()` adds only a check that at least one funding settlement exists inside each scored fold. A CSV with one valid settlement in a long fold can therefore pass this part of the preflight. Missing settlement rows are not detectable by comparing the remaining timestamps with Mark candles: Mark candles exist at many timestamps where no funding event is due.

## Minimal counterexample

Suppose the authoritative Bybit response for a symbol and period contains settlements at T1, T2 and T3. The local funding CSV accidentally omits T2. If Mark candles exist at T1 and T3, then:

- all remaining funding timestamps have a matching Mark candle;
- the funding set is non-empty;
- no duplicate exists;
- the Trade/Mark candle grids can still match.

The current validator has no expected-event input against which to detect the missing T2. This is a logical code-path counterexample, not a claim that a particular committed archive is corrupt.

## Impact

**Potential P1 PnL understatement of costs / overstatement of strategy net PnL.** Missing positive funding payments reduce modeled costs; missing negative funding receipts can also bias PnL in the opposite direction. The direction and magnitude depend on the missing events and position side. Until source completeness is evidenced, funding-adjusted Net PnL is not independently validated.

This finding does not invalidate the existing unit tests for funding arithmetic. Those tests validate cashflow calculations for supplied events; they do not validate archive completeness.

## Why a hard-coded 8-hour gap rule is not an acceptable quick fix

Bybit funding intervals are instrument-dependent and may change. A fixed 8-hour cadence check could reject valid data or accept an incorrect schedule. The current `InstrumentSpec` dataclass does not retain a dated funding interval, although the raw Bybit instrument payload can contain it. Any schedule-based check must be backed by dated source evidence and handle interval changes explicitly.

## Required remediation before H1 PnL validation

1. Extend the archive collector to write a per-symbol collection manifest containing endpoint/category/symbol, requested UTC start/end, every pagination window/cursor, page counts, response row counts, first/last returned settlement timestamps, API base, collection timestamp, and SHA-256 of the resulting CSV.
2. Preserve dated funding-interval metadata (or another authoritative schedule) with the instrument snapshots. Do not infer a universal cadence.
3. Add a validator that compares the funding CSV against the evidenced API query coverage and the applicable dated settlement schedule, and fails closed on unexplained gaps or incomplete boundary coverage.
4. In the portfolio runner, require and hash the funding completeness manifest alongside the CSV; include it in selection provenance and final validation manifest.
5. Add a regression fixture where one middle settlement is removed while all remaining timestamps still have Mark candles. The current validator should demonstrate the blind spot; the remediated validator must reject it. Add interval-change and boundary-coverage fixtures.
6. Keep the existing arithmetic tests separate from archive-completeness tests.

## Decision

- Do not run another H1 market PnL replay until this gate is closed.
- Do not alter funding arithmetic or assume a fixed 8-hour schedule as part of this audit.
- No strategy parameters, execution rules, or historical results were changed.
- No Bybit API, new archive collection, self-hosted runner, or live order was used.


## Implementation progress — 2026-11-03

The following guardrails have now been added on this research branch:

- `funding_archive_manifest.py` writes an atomic sidecar manifest with the API endpoint/base, category/symbol, requested time window, page request windows, response row counts, returned timestamp bounds, collection time, CSV SHA-256 and row count. Multiple incremental collection runs are preserved.
- `bybit_downloader.py` records each Funding pagination page and writes/updates the sidecar after collection.
- `validate_funding_manifest()` verifies CSV hash/row count and that recorded page query windows cover the scored interval.
- `validate_funding_mark_coverage()` now refuses H1 replay unless a matching sidecar exists, its query coverage spans the scored fold, and dated settlement schedule evidence is explicitly marked verified.
- The funding sidecar is included in both train-only selector input provenance and final H1 validation input manifests. The helper and collector are included in replay code provenance.
- Offline regression tests cover pagination metadata, incremental manifest preservation, hash tampering, query-window gaps, and fail-closed runner behavior.

**Important remaining limitation:** the collector deliberately writes `settlement_schedule_verified: false`. Query logs and a CSV hash prove what was requested/received and whether the CSV changed; they do not independently prove that Bybit returned every settlement event. No code path should set this flag to true until a dated, source-backed funding interval schedule is reconstructed and validated over the scored period. Thus this implementation improves provenance and blocks unverified archives, but it does not yet close the schedule-completeness requirement. Market PnL replay remains prohibited.


### Stronger schedule-evidence validation

The initial boolean schedule flag was replaced by a required sidecar reference to a separately hashed schedule JSON. The validator now checks the schedule file hash, symbol/category/source identity, coverage boundaries, ordered source-snapshot references and hashes, each referenced raw Bybit instrument snapshot's schema/category/fetched_at/symbol/fundingInterval, and exact equality between expected and observed settlement timestamps inside the scored interval. The H1 gate therefore cannot be satisfied by setting a bare boolean. A schedule-generation process based on complete dated snapshots is still not available for the historical archive, so replay remains blocked.


### Dated interval alignment check

The schedule validator also rejects unsupported interval values and requires every expected settlement timestamp to align with the applicable preceding snapshot's recorded interval. Bybit's V5 Funding Rate History documentation explicitly says each symbol can have a different interval and points to Instruments Info for that interval; the H1 gate therefore must not use a global hard-coded cadence. The implementation accepts the documented 1h/2h/4h/8h interval values and uses UTC-aligned settlement boundaries. See the official API documentation: https://bybit-exchange.github.io/docs/v5/market/history-fund-rate and https://bybit-exchange.github.io/docs/v5/market/instrument.


### Incremental-download integrity protection

The Funding downloader now verifies an existing sidecar's CSV SHA-256 and data-row count **before** making an incremental API request or appending new rows. If the existing CSV has drifted from its last manifest, the downloader refuses to extend or re-attest it. This closes a provenance-reset loophole where a modified historical CSV could otherwise receive a fresh hash during a later append. Offline regression coverage was added.


## Verification status

Research CI run [#41712039475](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41712039475) completed successfully: 50 workflow steps succeeded, including the H1 selector, H1 runner execution gate, validation-manifest provenance, portfolio accounting/risk-budget, and sparse shared-capital replay tests. The incremental-download tamper regression is included in that successful run.

This validates the code-level guardrails and synthetic/offline fixtures. It does **not** validate a real Bybit historical funding archive, produce a profitable strategy result, or authorize market PnL replay. The current production archive cannot pass until actual dated instrument snapshots and a matching generated schedule evidence file cover each scored interval.


### Active workflow collector integration — 2026-11-03

The first implementation touched the legacy root-level `bybit_downloader.py`. Repository workflow inspection then showed that the manual Bybit archive workflow actually executes `scripts/archive_bybit_market_history.py`. The active collector is now integrated too:

- Each Funding API page is recorded with its inclusive query bounds, response count, first/last timestamp, and `complete`/`saturated` status.
- A page returning the 200-row limit is explicitly marked incomplete; the collector recursively subdivides the requested time window. The manifest validator counts only complete leaf windows toward query coverage.
- After writing each symbol's Funding CSV, the active collector writes the matching `SYMBOL.csv.audit.json` sidecar with SHA-256, row count and all page metadata.
- The archive-level manifest now includes the active collector script SHA-256 and per-symbol Funding sidecar/hash references.
- The H1 replay code provenance list now includes `scripts/archive_bybit_market_history.py`, not only the legacy downloader.
- An integration regression test calls `archive_symbol()` with mocked market responses and verifies the sidecar is produced.

The sidecar still intentionally has no settlement schedule evidence. The archive workflow receives one point-in-time universe snapshot; it cannot be treated as a historical funding-interval schedule for an arbitrary multi-month archive. H1 market PnL remains blocked until dated schedule evidence spans the scored interval.


### Final active-collector guardrails and CI

Additional protections:
- Active collector output roots are immutable: if a Funding CSV, its audit sidecar, trade-kline CSV, or mark-price CSV already exists for the symbol, the collector refuses to overwrite the output root. This prevents a rerun from silently replacing prior evidence.
- Duplicate Funding timestamps returned by Bybit are rejected, even if the duplicate rows are identical.
- The manifest validator counts only pages explicitly marked complete; a saturated 200-row parent response cannot attest its full request window. Recursive complete child windows must cover the entire requested interval.
- The active collector now adds its own script SHA-256 to the archive-level manifest, and H1 replay code provenance hashes this active collector.

Research CI [#41713006331](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41713006331) completed successfully: 50 workflow steps, zero failures. This includes the active archive collector integration test, duplicate-timestamp regression, saturated-page coverage tests, funding manifest checks, H1 execution/provenance gates, portfolio accounting, and sparse shared-capital replay.

The gate is still intentionally not green for real H1 PnL: no actual Bybit archive sidecars or dated funding schedule evidence exist in the repository.
