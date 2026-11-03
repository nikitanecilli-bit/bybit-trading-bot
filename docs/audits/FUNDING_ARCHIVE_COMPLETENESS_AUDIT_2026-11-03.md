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
