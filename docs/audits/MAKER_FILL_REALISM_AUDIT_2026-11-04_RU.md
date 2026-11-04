# Maker fill realism audit — 2026-11-04

Branch: `research/market-regime-v1-main`  
Scope: entry/TP fill classification, fee/slippage accounting, OHLC limit-fill stress runners.  
Method: source inspection against `Bybit_Trading_Engine_v14_research.py`, `tests/test_gap_execution.py`, `scripts/run_execution_cost_ablation.py`, `scripts/run_execution_walk_forward.py`, and `scripts/run_h1_limit_fill_stress.py`.  
No market PnL replay, API account query, or live order was run.

## Executive decision

**Maker execution is not validated.** The current engine distinguishes a marketable limit gap at the candle open from a later intrabar touch, but the latter is only an OHLC fill proxy. It cannot establish queue position, executable size, or whether a passive order would have filled before price reversed.

Keep OHLC maker results labelled as an optimistic execution scenario / upper bound. Do not treat the fee saving as realised edge and do not promote a maker-based PnL result to production evidence.

## Confirmed implementation

### 1. Entry classification

- A limit order that is already marketable at the next candle open is converted to effective `market` entry classification; this charges taker fee and taker slippage. Long buy gap-through and short sell gap-through have regression coverage in `tests/test_gap_execution.py`.
- A non-marketable limit whose candle later reaches the limit is still classified as `limit` (maker proxy). This is not exchange-confirmed maker execution.
- The position sizing path receives the effective entry order type, so a gap-through that is reclassified as market uses taker costs in the risk estimate.

### 2. Exit classification

- Stop loss, trailing stop, time stop, breakout-retest invalidation and kill-switch exits are passed to close accounting as taker.
- TP1/TP2 target exits can be classified as maker when maker exits are explicitly enabled and the target was not already marketable at the candle open.
- A target already marketable at candle open is classified as taker. The current OHLC model books the target price rather than the more favourable opening price in these gap-through target cases; this is conservative for gross PnL, although fee notional is then also based on the target price.
- Same-candle stop/target ambiguity is resolved in favour of the stop. This is a conservative ordering convention, not reconstructed event order.

### 3. Cost constants

The engine currently hardcodes the following per-leg assumptions:
- taker fee: `0.00055` (0.055%);
- maker fee: `0.00020` (0.020%);
- taker slippage cost: `0.000225` (0.0225%);
- maker slippage: zero.

These are baseline constants, not a verified fee schedule for this user's account, symbol, date, or VIP tier. They are applied to entry/exit notionals in the journal; position sizing also reserves the assumed entry and taker-stop costs. The slippage constant is booked as a cost rather than shifting the simulated fill price.

### 4. Existing stress runners

- `run_execution_cost_ablation.py`: isolates maker-entry savings; explicitly models all exits as taker. It uses fixed-price OHLC touches and documents missing queue/spread/partial-fill/adverse-selection effects.
- `run_execution_walk_forward.py`: compares market and limit-offset candidates, but still relies on OHLC touch fills and modelled costs.
- `run_h1_limit_fill_stress.py`: adds 0/5/10 bps extra penetration before counting an intrabar limit touch, but it is still a candle-range threshold, not a queue-volume or fill-probability model.
- These runners use Binance/CryptoFetch proxy OHLCV datasets, not a verified Bybit historical order-book/trade stream.

## What OHLC cannot prove

A candle touching or penetrating a limit price does not reveal:
1. whether the best bid/ask was at the assumed price when the order arrived;
2. queue volume ahead of the order or whether traded volume consumed that queue;
3. whether the order was partially filled, and at what timestamps/prices;
4. cancel/replace latency and whether a stale order remained live during a reversal;
5. adverse selection after passive fills;
6. spread, depth and market impact for the requested quantity.

Adding a fixed penetration threshold does not solve these unknowns. It only makes the OHLC touch condition stricter.

## Required evidence before calling maker edge credible

For a fixed, frozen symbol universe and period, collect timestamped Bybit public data:
- best bid/ask and depth snapshots or incremental order-book updates;
- public trades with side, price, quantity and timestamp;
- instrument tick/qty specs and trading status as-of the test date;
- fee schedule applicable to the account tier (or explicitly retain a fee sensitivity range).

Then implement a conservative replay:
- join order arrival to the contemporaneous book/trade stream;
- model queue ahead and consume it only with eligible opposing aggressor volume;
- support partial fills, cancellations, latency and unfilled expiry;
- apply adverse-selection measurement after fills;
- charge maker/taker fees from the actual execution classification;
- compare against market entry using identical signal timestamps, position sizing policy, exits and capital constraints.

If complete L2/trade history is unavailable, report bounded scenarios only (e.g. zero, partial and low fill rates) and never label them as observed fills. Do not infer a fill rate from OHLC alone.

## Changes and validation

- This audit is documentation-only; engine behavior, strategy parameters, fees, and datasets were not changed.
- No new historical PnL was generated.
- Existing deterministic Research CI remains the relevant code validation; green CI does not validate queue execution or account-specific fees.

## Decision

`MAKER_EXECUTION_REALISM = BLOCKED`

Continue using maker scenarios only as sensitivity bounds. Next work should focus on obtaining Bybit-native order-book/trade history or establishing a transparent fill-rate bound; do not run another strategy parameter sweep to compensate for missing execution evidence.


## Newly identified official Bybit historical-data route

The previous blocker should be refined: the repository has no order-book/trade archive collector and the existing REST download attempts returned HTTP 403 from GitHub Actions, but Bybit's official documentation points to a separate historical-data download portal.

- Bybit V5 `Get Recent Public Trades` explicitly says archived historical trades can be downloaded from the website: https://bybit-exchange.github.io/docs/v5/market/recent-trade
- Bybit's official guide says historical public market data is downloadable as CSV and includes order-book snapshots, K-line, trade and funding data: https://www.bybit.com/en/learn/bybit-guide/how-to-create-a-bybit-api-key
- Portal: https://www.bybit.com/en/derivative-activity/history-data

This is a promising non-API-key route and may avoid the GitHub Actions REST-host 403. **Availability is not yet verified** for the exact linear symbols, date ranges, depth granularity, update cadence, and file formats needed by our frozen H1 universe. The portal page is dynamically rendered in the accessible web view, so no downloadable dataset has been claimed or committed.

Next safe acquisition step: inspect the portal's product/category filters, then download a small representative BTCUSDT + one lower-liquidity target-symbol sample for a short date window. Validate schema, timestamps, sequence/update IDs, coverage and file hashes before attempting a full universe export. Do not treat a single order-book snapshot per minute as a queue replay; the feed cadence must be sufficient to reconstruct order arrival and consumption around each hypothetical order.
