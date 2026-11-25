# OKX public archive — QA report (2026-11-25)

## Decision

**D1 (OKX-native H1 trade OHLCV): PASS for the captured 365-day interval.**  
**D2 (OKX H1 Mark Price): PASS for the same interval as a reference-price series.**  
**D3 (Funding): PARTIAL; 278 normalized events over approximately three months, completeness not established.**  
**D5 (instrument specifications): current snapshot only; historical effective-time specifications NOT ACCEPTED.**  
**D4 lifecycle history, D6 historical risk tiers, and D8 dated fee assumptions remain NOT ACCEPTED / not established.**

This archive is a successful public-data source pilot. It is not evidence of a trading edge, Bybit execution conditions, or an independent calendar-time holdout.

## Capture provenance

- Exchange: OKX official public REST host, `https://www.okx.com`
- Instrument: `BTC-USDT-SWAP` (linear, USDT-settled swap)
- Capture: 2026-11-25 08:02–08:03 UTC
- GitHub Actions run: [45572813249](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45572813249), completed / success
- Branch: `research/okx-public-data-loader`
- Credentials: none
- Endpoints: H1 history candles, H1 history mark-price candles, public funding-rate history, current SWAP instrument metadata
- No private/account endpoints, keys, orders, strategy execution, PnL, or backtests were used.

Requested H1 interval is half-open:
- Start inclusive: `2025-11-25T08:00:00Z`
- End exclusive: `2026-11-25T08:00:00Z`
- Duration: 365 days / 8,760 hours

## Integrity and coverage checks

- 88 trade-candle pages; 8,800 raw rows returned before requested-range clipping.
- 88 Mark Price pages; 8,800 raw rows returned before requested-range clipping.
- 3 Funding pages; 279 raw events returned before requested-range clipping.
- One current instrument metadata response.
- All 179 paginated raw responses returned OKX `code=0`.
- All 179 raw page byte lengths and SHA-256 hashes match the manifest.
- Instrument raw response byte length and SHA-256 match the manifest.
- All three normalized CSV SHA-256 hashes match the manifest.
- No duplicate timestamps across raw pages within each dataset.
- Pagination page boundaries are strictly ordered with no repeated cursor timestamp.
- Trade and Mark Price normalized series each contain exactly 8,760 unique hourly rows.
- Both H1 grids cover the requested interval continuously; no missing hours.
- All 8,760 normalized H1 rows in each series have `confirm=1`.
- OHLC consistency checks passed; all OHLC values are positive.
- Trade and Mark Price timestamps match exactly across all 8,760 rows.

The raw endpoints include records at/around the exclusive end boundary; normalized CSVs correctly clip to the requested half-open interval. The latest in-progress candle is therefore not counted as a completed row.

## Funding findings

- 278 normalized settlement events.
- Coverage: `2026-08-24T16:00:00Z` through `2026-11-25T00:00:00Z`.
- All 277 observed adjacent intervals are 8 hours.
- Observed `formulaType=withRate` and `method=current_period` on all normalized rows.
- Funding rate range in this sample: -0.0000641996 to 0.0001.
- The endpoint did not reach the requested 365-day start. OKX documents this history endpoint as having up to three months of history.

The observed 8-hour cadence describes this captured sample only. It must not be generalized into a permanent settlement schedule. A complete funding ledger requires an effective-time settlement schedule/formula-regime audit and adequate historical coverage. Funding D3 is therefore **not accepted**.

## Current instrument metadata snapshot

Captured fields:
- `state=live`
- `ctType=linear`
- `ctVal=0.01`
- `ctValCcy=BTC`
- `settleCcy=USDT`
- `tickSz=0.1`
- `lotSz=0.01`
- `minSz=0.01`
- `lever=100` (exchange metadata maximum; not a leverage recommendation)
- `listTime=1573557408000`

These values describe the response captured on 2026-11-25 only. They do not establish historical values or changes over the 365-day period. D5 remains open. D6 risk tiers are not included in this pilot.

## Research interpretation

1. The OKX public endpoints and backward pagination work from the GitHub-hosted runner.
2. A verified one-year H1 trade and Mark Price archive is now available for one instrument.
3. This is a different venue, but it is not automatically an independent time holdout. Calendar overlap with previously explored periods remains overlap.
4. It cannot establish Bybit execution quality, fee schedule, lifecycle, contract-spec history, or risk tiers.
5. No market-PnL calculation or strategy test is authorized by this data-source pilot.

## Next constraint and permitted next work

The immediate data constraint has shifted: H1 candles and Mark Price are available for this OKX instrument. Remaining blockers are:
- complete/effective-time Funding history and formula/settlement schedule;
- historical lifecycle and instrument specifications;
- dated fee assumptions;
- a genuinely independent validation period and venue/execution alignment for the intended deployment venue.

Next work should be a read-only documentation/evidence review of OKX historical-data and contract-rule coverage, without expanding the collector to more instruments or endpoints until the gap and value are clear. No PnL/backtest/sweep/event study should begin without a separate explicit authorization.
