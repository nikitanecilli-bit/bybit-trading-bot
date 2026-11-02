# ENG-FUND-002 — funding receipt when the position fully closes at settlement boundary

Статус: ACCEPT — confirmed by test-first failure and passing regression CI.
Дата: 2026-11-02.
Тип: deterministic accounting/risk correctness; no market experiment.

## Confirmed lifecycle path

`_manage_position()` can set TP1 and TP2 at the same candle-close timestamp, then immediately call `_close_position()`. A stop can also close the full position at that timestamp without TP1. The funding helper currently knows TP1 time and remaining fraction, but not the final close timestamp.

## Hypothesis

If a funding settlement shares the final close boundary, OHLC cannot establish whether settlement occurred before or after the full exit. For conservative PnL:
- funding payment: charge full initial quantity;
- funding receipt: credit zero quantity.

Current behavior can credit a receipt on 50% remaining quantity after TP1+TP2 at the same boundary, or 100% when a stop closes the position without TP1. This can overstate trade PnL.

## Preregistered change

Add an optional final-close timestamp to `accrued_funding_cost()`. When a settlement timestamp equals the final close timestamp, use full initial quantity for a payment and zero quantity for a receipt. Preserve existing TP1-boundary behavior when the position remains open or final close occurs later. Wire `_close_position()` to pass its exit timestamp.

Separately test MTM at the settlement boundary: because the current engine marks portfolio equity before managing candle exits, receipts at the current as-of boundary must not optimistically mask adverse risk before the exit is resolved. If the existing sequencing cannot support a safe, causal policy without restructuring, document it as a separate blocker rather than silently changing event order.

## Tests

- Long/short receipt at final-close boundary -> zero credited amount.
- Long/short payment at final-close boundary -> full initial quantity charged.
- TP1 and full TP2 exit at same boundary -> no receipt on remaining half.
- Stop/full exit at settlement boundary with no TP1 -> no receipt.
- Settlement strictly before final close -> normal exposure quantity applies.
- Existing TP1 partial, pre/post TP1, cumulative, duplicate and missing-mark cases remain unchanged.

## Scope

No strategy changes, parameter search, market backtest, private API request or live order. Accept only after regression tests and Research CI pass.


## Реализация и результаты (2026-11-02)

- Test-first commit: `b06524c6ce0613322169b33892fb8896ad5f720a`.
- CI [#41502110789](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41502110789) reproduced the missing final-close context: four new cases failed with `TypeError: unexpected keyword argument 'closed_ts_ms'`.
- Fix: `accrued_funding_cost()` now accepts optional `closed_ts_ms`; at exact full-close boundary, payments use full initial quantity and receipts use zero. `_close_position()` passes its final exit timestamp.
- Added engine-level trade-ledger tests for both receipt and payment at the final-close boundary.
- Full Research CI [#41502251992](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41502251992) completed SUCCESS. Funding boundary, realized funding, MTM funding, portfolio accounting and all other configured suites passed.
- Decision: ACCEPT for realized trade PnL accounting. No market backtest or live operation.
- Remaining issue tracked separately in ENG-FUND-003: pre-exit MTM currently runs before candle exit resolution and may temporarily credit a receipt at the current as-of boundary.
