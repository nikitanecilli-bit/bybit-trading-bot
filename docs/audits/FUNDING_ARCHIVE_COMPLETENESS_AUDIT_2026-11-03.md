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


### Remaining schedule-validator trust boundary — 2026-11-03

A further static review of `validate_funding_manifest()` found a limitation in what the schedule evidence currently proves:

- It compares the Funding CSV timestamps with `expected_settlement_timestamps_ms` supplied inside the schedule JSON.
- It checks that each supplied expected event is aligned to the most recent preceding instrument snapshot's `fundingInterval`.
- It checks that source snapshots bracket the scored interval.
- It does **not** independently derive every expected settlement timestamp from the dated interval history, and it does not enforce a maximum observation gap or prove the effective timestamp of an interval change.

Therefore, if a Funding settlement is absent from both the CSV and the supplied expected-event list, those two incomplete artifacts can still be internally consistent. The hash protects the schedule file from later modification; it does not prove that the list was generated completely. Likewise, a snapshot's `fetched_at` is an observation time, not proof of the exact effective time of a Funding interval change.

This does not establish that any current archive is missing an event. It establishes that the current validator is a consistency check against supplied schedule evidence, not an independent proof that the schedule itself is complete.

**Decision:** keep the H1 market-PnL gate closed. Do not claim Funding completeness solely because `validate_funding_manifest()` returns `ok`. Closing this gap requires an authoritative, independently auditable source for historical interval effective times (or an independently generated schedule with verifiable completeness provenance). Do not infer change-effective timestamps from snapshot fetch times, and do not invent a fixed 8-hour cadence.


### Independent UTC-grid reconstruction — 2026-11-03

The validator has been strengthened after this review:

- For a scored interval whose dated instrument snapshots all report the same fundingInterval, it independently reconstructs the UTC settlement grid from that interval and the required start/end timestamps.
- It compares the supplied expected-event list, restricted to the scored interval, with the reconstructed grid. A CSV and schedule that both omit the same settlement now fail.
- If observed snapshots report different funding intervals, validation fails closed with funding_interval_changed_without_effective_boundary_evidence. A snapshot fetch time is not silently treated as the exact effective time of the change.
- Regression tests cover a matching-but-incomplete CSV+schedule pair and an unresolved interval transition.

Bybit's current public contract terms list 1h, 2h, 4h and 8h settlement grids in UTC (1h on every hour; the other intervals at their corresponding UTC multiples). The validator's grid reconstruction is limited to those documented intervals and does not hardcode 8h.

**Important residual limitation:** matching snapshots do not prove that an interval never changed and reverted between observations. The current collector is manual and live snapshot acquisition is blocked by HTTP 403; it does not produce a continuous historical interval series. The reconstructed grid is therefore an independent consistency check conditional on interval stability evidenced by the snapshots, not a cryptographic proof that no unobserved historical interval change occurred. Until authoritative historical effective-time evidence or sufficiently complete independently verifiable observations exist, the market-PnL gate remains closed.

The new Funding archive manifest and downloader tests were previously absent from Research CI's execution list. They have now been added to research-checks.yml, including the modified-CSV incremental-download regression. The updated CI result is pending at the time of this note.


### Saturated-page pagination coverage — 2026-11-03

A second implementation issue was found in the archive query-provenance gate. The downloader paginates backward by setting the next request end to one millisecond before the oldest timestamp returned. However, the validator previously discarded every saturated 200-row page from query-coverage accounting. It therefore could not certify the upper segment of a normal multi-page archive, even when the subsequent page windows covered the earlier segment without a gap.

Correction:
- The collector now records whether the API response timestamps are descending and unique.
- The validator counts a saturated page's upper segment from its oldest returned timestamp through that request's end time, but only when the response has exactly 200 unique descending timestamps.
- Complete earlier page windows must join that segment without gaps. A saturated page without ordering/uniqueness evidence remains unattested and fails closed.
- A 201-settlement fixture exercises one saturated 200-row page plus the final one-row page and verifies full-window coverage; the single saturated-parent test still verifies that a missing lower segment is rejected.

This relies on the endpoint's observed descending-page behavior used by the collector's backward pagination. The official endpoint documentation confirms a maximum of 200 records and that an endTime query returns records up to that time, but does not spell out response ordering in the parameter table; the collector therefore records and checks the returned order rather than silently assuming it.

Research CI [#41719390878](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41719390878) completed SUCCESS: **52/52 steps**, including Funding archive schedule reconstruction, saturated-page pagination coverage, downloader manifest integrity, H1 funding/Mark preflight, and the existing engine/accounting suite. This run used commit `ebc6721c51cd0c397e35bbae5631dda429a2882f`.


### Follow-up verification — 2026-11-04

The reconstructed-grid regressions are now part of the active Research CI workflow rather than merely existing as unexecuted test files. The workflow also executes the active downloader-manifest regressions and H1 runner fail-closed fixtures.

Research CI [#41726204938](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41726204938) completed **SUCCESS, 53/53 steps**, at commit `2f7c590e70da47ab855db31d9f823d8134ac7cd5`. Funding-specific passing steps include cumulative Funding accounting, realized Funding PnL, Mark-to-market Funding risk, Funding/Mark preflight, Funding archive provenance and schedule completeness, and downloader manifest integrity.

This verifies the new code paths against synthetic/offline fixtures. It does **not** remove the residual trust boundary described above: the currently available snapshots cannot rule out an interval change and reversion between observations, and no actual Bybit funding/Mark archive with historical schedule evidence exists. The market-PnL gate remains CLOSED.


### Production archive attachment path — 2026-11-04

A separate operational gap is now closed in code: the official archive workflow previously wrote Funding query provenance but left `settlement_schedule_evidence=null`, while the H1 runner requires a verified dated schedule. The archive produced by that workflow therefore could never pass the H1 Funding gate without manual sidecar construction.

Implemented:
- `funding_archive_manifest.attach_funding_settlement_schedule()` builds a UTC settlement grid from hash-pinned Bybit instruments-info snapshots, copies the exact source snapshots into the archive, and updates the Funding manifest atomically.
- `scripts/archive_bybit_market_history.py` now requires `--instrument-snapshot-dir` and attaches schedule evidence for each symbol.
- The official `bybit-market-history-archive.yml` workflow now fails before downloading if dated instrument snapshots are absent and passes `data/instrument_specs/linear` to the collector.
- The helper chooses the nearest matching-symbol snapshot at/before the requested start and at/after the requested end, includes observations between them, ignores snapshots outside that symbol's observed lifecycle window, and fails closed if the symbol disappears inside the bracket or if an observed Funding interval changes.
- Offline tests verify that the production collector emits a schedule sidecar accepted by the validator, and that an observed interval change with unknown effective boundary is rejected.

Research CI [#41729833792](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41729833792) completed **SUCCESS, 55/55 steps**, including Bybit market-history archive collector tests and Funding archive provenance/schedule-completeness tests. Tested commit: `7653ae9991f10e137f32c51c7665ade421cec585`.

Residual limitation is explicit: point-in-time snapshots cannot rule out an interval change and reversion between observations. The snapshot workflow has previously been blocked by Bybit HTTP 403 and no real dated Bybit instrument/risk, trade-kline, Funding or Mark archive is committed. This is an offline implementation result only; the H1 market-PnL gate remains CLOSED.


### Official API history boundary — 2026-11-04

Checked the current official V5 endpoint documentation. `GET /v5/market/funding/history` returns historical funding rates/timestamps and explicitly says each symbol has its own funding interval, directing clients to `instruments-info` to query that interval. `GET /v5/market/instruments-info` exposes `fundingInterval` as a response field, but the documented endpoint is a current instruments-info query; no historical effective-time query for past interval changes is documented.

Sources:
- https://bybit-exchange.github.io/docs/v5/market/history-fund-rate
- https://bybit-exchange.github.io/docs/v5/market/instrument

Therefore, a present-day interval value cannot be back-projected across an old Funding archive. The new collector deliberately requires dated snapshots that bracket the archive range. If no snapshot exists before the requested start or after the requested end, it must reject the archive rather than silently assume the current interval applied historically. Even daily point-in-time snapshots cannot prove that an interval did not change and revert between observations; that residual uncertainty stays explicit.
