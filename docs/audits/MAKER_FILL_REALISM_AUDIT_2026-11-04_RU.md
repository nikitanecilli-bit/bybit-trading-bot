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


### Fee-rate verification against current public schedule

The two engine fee constants do match Bybit's published **VIP 0 / non-VIP baseline** for perpetual and futures contracts: maker 0.0200%, taker 0.0550%. However, Bybit's current fee-structure page (last updated 2026-09-02) explicitly says rates vary by VIP/Pro tier and region, and the applicable account rate should be checked in My Fee Rate. Thus the constants are reasonable baseline defaults, not evidence of the user's actual rate.

Official references:
- https://www.bybit.com/en/help-center/article/Trading-Fee-Structure
- https://www.bybit.com/en/help-center/article/FAQ-USDT-Perpetual-and-Expiry-Contracts

The 0.0225% per-leg taker slippage constant is not a published Bybit fee. It remains a local modelling assumption and needs symbol/time/size-specific execution evidence.


## 5. Проверка реальных Bybit L2 и public trades архивов (2026-11-04)

### 5.1 CDN reachability and candidate-universe coverage

A bounded HEAD + HTTP Range probe ran from GitHub Actions against three dates:
- 2024-12-01: legacy `ob500`;
- 2025-09-02: `ob200`;
- 2026-09-02: `ob200`.

Each successful object returned HTTP 200 to HEAD and HTTP 206 to `Range: bytes=0-4095`; only one byte of the returned range body was read. No full archive was downloaded during this coverage probe.

The probe covered the current H1 shortlist from `scripts/h1_symbol_universes.json` plus the legacy liquidity universe and the Bybit PEPE contract alias.

| Candidate group | Symbols | Result on all three sampled dates |
|---|---|---|
| Primary | TAOUSDT, AAVEUSDT, CAKEUSDT | 3/3 available each |
| Reserve | DASHUSDT, HBARUSDT, ENAUSDT, GMXUSDT, ONDOUSDT | 5/5 available each |
| Primary/reserve gaps | RAYUSDT, PUMPUSDT | 404 each date |
| Legacy/liquidity references | BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, BNBUSDT, SUIUSDT | 7/7 available each |
| PEPE Bybit contract name | 1000PEPEUSDT | 3/3 available |
| Incorrect/unverified alias | PEPEUSDT | 404 each date |

The RAY/PUMP 404 results mean only that these exact archive objects were absent at the tested paths/dates. They do not prove that the contracts were never listed or that no alternate historical feed exists. The point-in-time Bybit instrument snapshot is still not available, so do not silently drop or rename either candidate.

**Confirmed symbol-mapping issue:** the official Bybit fee-group documentation lists `1000PEPEUSDT`; the tested Bybit L2 archive also exists under that exact symbol. The older Binance-style OHLCV screening report used `PEPEUSDT`. Treat these as different venue identifiers until Bybit instrument metadata confirms the contract unit, tick size and quantity step. Do not send `PEPEUSDT` to the Bybit execution layer as a substitute for `1000PEPEUSDT` without an explicit, tested mapping.

Coverage probe: [Research workflow #41810416421](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41810416421). The report is an artifact of that run.

### 5.2 Full one-day AAVEUSDT L2 archive integrity

A complete one-day sample was downloaded inside a disposable GitHub runner, scanned to EOF, and not committed to the repository.

- URL: `https://quote-saver.bycsi.com/orderbook/linear/AAVEUSDT/2025-09-02_AAVEUSDT_ob200.data.zip`
- Compressed bytes: 88,252,368
- SHA-256: `e3646429c600f4917c021e240497e8f3d46fd44ba57168100633181916c761f6`
- JSONL events: 816,684 = 2 snapshots + 816,682 deltas
- Depth: 200 bid and 200 ask levels in snapshots
- Coverage: 24 hours; all events include `cts`
- Non-monotonic `ts`: 0; non-monotonic `seq`: 0; adjacent duplicate timestamps: 0; `u=1` resets: 0
- ZIP stream reached EOF and passed its CRC check through the standard ZIP reader.

This validates the archive container and its event schema for this one symbol/day; it is not a full multi-month completeness audit.

### 5.3 Matching public trades archive

The matching AAVEUSDT trade archive was also fully downloaded and streamed to EOF:

- URL: `https://public.bybit.com/trading/AAVEUSDT/AAVEUSDT2025-09-02.csv.gz`
- Compressed bytes: 13,095,906
- SHA-256: `cf11d05f6053acfeb22b1112df666ff328034963f04c6e6159f35cae63de1bc1`
- Rows: 346,131; unique `trdMatchID`: 346,131; duplicate IDs: 0
- Non-monotonic trade timestamps: 0
- Taker/aggressor side: Buy 176,411; Sell 169,720
- Total contract size: 338,330.20; notional: 105,423,139.2883 USDT
- `RPI` column present; all 346,131 rows have value `0`
- No `isBlockTrade` field in this archive schema.

Trade timestamps were compared to the L2 matching-engine `cts` range (not the local/server `ts`):
- 346,065 trades fall inside the L2 `cts` range;
- 66 trades precede the first available book snapshot;
- 0 trades occur after the last book `cts`;
- the first trade is 1,276 ms before the first book `cts`; the final trade is 5,177 ms before the final book `cts`.

The 66 early trades must be excluded from a replay that starts from the first L2 snapshot; the remaining overlapping interval is suitable for a first queue-model prototype. Do not extrapolate the boundary coverage result to other symbols/days without measuring it.

Full sample-inspection workflow: [#41810648340](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41810648340); the follow-up overlap/RPI report is [#41810769292](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41810769292).

### 5.4 What is now possible — and what is still not proven

The archive pair is sufficient to prototype an aggregate L2 queue lower-bound model:
1. Rebuild the visible book from snapshots and deltas.
2. At hypothetical order arrival, classify a marketable order using contemporaneous best bid/ask; otherwise initialize queue-ahead with the displayed size at the limit price.
3. Decrement queue-ahead only with eligible opposing-aggressor trades at that exact price; support partial fills.
4. Do not credit cancellations as queue-ahead reductions. L2 deltas cannot distinguish cancellation from execution or identify whether a cancellation was ahead of or behind the hypothetical order.
5. Exclude trades explicitly marked RPI where the archive supplies the flag; report archive schemas without a block-trade flag as a limitation.
6. Apply explicit order-arrival and cancel latency; never use trades at or before the order-arrival timestamp to fill the hypothetical order.

This remains an aggregate L2 lower-bound approximation, not L3 queue reconstruction or exchange-confirmed fills. RPI/block trades, hidden liquidity, same-timestamp ordering and market impact still require careful handling.

**Decision unchanged:** `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`. Data acquisition is now feasible and one matched day passed integrity checks. The next safe engineering step is a separate, deterministic queue-replay prototype with synthetic tests and a measured AAVE sample; only after that should it be connected to H1 strategy signals. No strategy PnL was run in this data-validation stage.
