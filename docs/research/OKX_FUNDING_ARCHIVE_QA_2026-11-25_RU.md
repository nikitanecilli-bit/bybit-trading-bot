# OKX BTC-USDT-SWAP — one-year market and funding archive QA

**Capture date:** 2026-11-25  
**Research branch:** `research/okx-public-data-loader`  
**Funding capture run:** [GitHub Actions 45576601291](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45576601291) — success  
**Artifact:** `okx-btc-usdt-swap-funding-monthly-archives` (artifact ID `15004027490`, 7-day retention)  
**Funding CSV SHA-256:** `80ec71a9a732f6027a30d6333a61f2f408ad365416b6a988305cdad848242b0b`

## Decision

- **D1 — H1 trade OHLCV: PASS** for the captured one-year interval.
- **D2 — H1 Mark Price: PASS** for the same interval.
- **D3 — realized funding event/rate coverage: PASS for one year**, with the explicit metadata limitation below.
- **D4 — historical lifecycle: PARTIAL / NOT ACCEPTED.**
- **D5 — effective-time historical instrument specifications: NOT ACCEPTED.** Only a current snapshot exists.
- **D6 — historical risk tiers: NOT ACCEPTED.**
- **D7 — L2/trades: DEFERRED** for a future conservative taker-only model; no maker/queue/capacity claims.
- **D8 — dated fee assumptions: NOT ACCEPTED.**

This is an OKX public-data source acceptance result for one instrument. It is not Bybit execution evidence, not an independent calendar-time holdout, and not a trading-edge result.

## H1 price data

Requested interval is half-open:
- Start inclusive: `2025-11-25T08:00:00Z`
- End exclusive: `2026-11-25T08:00:00Z`
- Duration: 365 days / 8,760 hours

The cloud capture contains:
- 8,760 H1 trade OHLCV rows;
- 8,760 H1 Mark Price rows;
- 88 raw pages for each series;
- continuous hourly grids, unique timestamps, no unfinished candles, positive and OHLC-consistent values;
- exact timestamp alignment between trade and Mark Price series.

All raw response hashes and normalized CSV hashes match the capture manifest.

## Funding archive recovery

The official public catalog endpoint `GET /api/v5/public/market-data-history` was used with module `3` (funding rate), `instType=SWAP`, `instFamilyList=BTC-USDT`, and monthly aggregation. The catalog returned all ten requested monthly files for November 2025 through August 2026.

The ten ZIPs were downloaded only from the official OKX CDN host `static.okx.com`, checked with ZIP CRC validation, and preserved with SHA-256 hashes. Each archive contains one CSV with columns:
- `instrument_name`
- `funding_rate`
- `funding_time`

Monthly rows:
- 2025-11: 90
- 2025-12: 93
- 2026-01: 93
- 2026-02: 84
- 2026-03: 93
- 2026-04: 90
- 2026-05: 93
- 2026-06: 90
- 2026-07: 93
- 2026-08: 93

Total archive rows: **912**, all unique, with 911 consecutive 8-hour intervals and no gaps across the archive range.

The REST endpoint `GET /api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=400` returned 279 rows at capture time. Of these, 278 fall inside the requested one-year half-open interval; the extra row at exactly `2026-11-25T08:00:00Z` is correctly excluded as the end boundary.

## One-year merged funding validation

The canonical one-year file `funding_history_1y.csv` was assembled with explicit source columns and no silent overwriting.

| Check | Result |
|---|---:|
| Archive rows inside requested interval | 838 |
| REST rows inside requested interval | 278 |
| Shared timestamps | 21 |
| Exact archive `funding_rate` vs REST `realizedRate` matches | 21 / 21 |
| Mismatches | 0 |
| Final unique merged events | **1,095** |
| Duplicate timestamps | 0 |
| Missing 8-hour slots | 0 |
| Adjacent interval | 1,094 × 8 hours |

The merged series starts at `2025-11-25T08:00:00Z` and ends at `2026-11-25T00:00:00Z`. The next 8-hour slot is exactly the exclusive end boundary.

This supports use of the monthly archive rate as the realized funding event value for this instrument: every one of the 21 shared timestamps matches the REST `realizedRate` exactly. The merged CSV preserves both source values and a per-row source label.

## Formula regime and metadata boundary

Official OKX announcements establish the following for BTCUSDT perpetuals:

1. OKX's 2025 formula migration placed BTCUSDT in the third batch, effective **2025-04-24 00:01 UTC**. The full one-year sample begins later, on 2025-11-25, so the entire sample is after this migration. Source: [OKX, 14 Mar 2025 announcement](https://www.okx.com/en-gb/help/okx-to-change-the-funding-rate-formula-for-perpetual-futures).
2. OKX announced a further 8/N formula revision effective from 2026-06-01, with migration by 2026-06-04. For an 8-hour settlement cycle (N=8), OKX states the per-period funding rate is unchanged. The captured event series has an 8-hour cadence throughout. Source: [OKX, 29 May 2026 announcement](https://www.okx.com/help/important-update-revision-of-the-funding-rate-formula-for-okx-perpetual).
3. The 279 REST rows expose `formulaType=withRate` and `method=current_period`. The monthly archive CSVs do not include either field. Therefore, the actual funding rate and settlement timestamps are complete for the one-year interval, and the formula epochs are documented, but the historical `method` field is not independently reconstructed for archive-only rows.

For realized funding-cost accounting, the published rate at each settlement timestamp is preserved as the event input. Do not use the missing historical `method` field to invent a predictive signal or claim that all API metadata has been reconstructed.

## Current instrument metadata

The separate current instrument snapshot reports a linear USDT-settled BTC swap with `ctVal=0.01 BTC`, `tickSz=0.1`, `lotSz=0.01`, and `minSz=0.01`. These are current values only. They do not establish historical contract specifications or risk tiers.

## Research interpretation and next constraint

- OKX now supplies a verified one-year BTC-USDT-SWAP H1 price, Mark Price, and realized funding-event dataset.
- This does **not** repair the Bybit data-access blocker or prove Bybit fills, fees, contract rules, or risk tiers.
- A different venue does not create a time-independent holdout if its calendar dates overlap periods already explored on Binance/proxy data.
- D4/D5/D6/D8 remain open as listed above.
- The existing H1 candidate is still not ready for an honest independent validation; do not launch PnL, backtests, sweeps, or event studies from this archive without separate authorization and a documented independent validation design.

No private/account endpoints, API keys, proxy, mirror, order placement, strategy execution, or PnL calculation were used.
