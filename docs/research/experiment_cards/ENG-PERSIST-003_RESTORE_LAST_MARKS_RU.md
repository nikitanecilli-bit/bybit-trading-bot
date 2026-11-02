# ENG-PERSIST-003 — restore last known marks for open positions

Статус: PREREGISTERED — test-first reproduction pending.
Дата: 2026-11-02.
Тип: recovery integrity / portfolio risk accounting.

## Наблюдение

`PlanBStatePersistence` saves risk equity and open positions, but does not save `_last_mark_prices`. After process restart, `UnifiedQuantEngine` initializes `_last_mark_prices` as an empty dict. `_unrealized_pnl_at_marks()` then falls back to each open position's entry price until a new candle arrives for that symbol. The first MTM after restart can therefore erase the previously marked PnL and omit price movement since entry for every not-yet-refreshed position. This can distort current equity, drawdown and risk budget while symbols refresh asynchronously.

## Hypothesis to prove

A restored position last marked materially away from entry is restored without its last mark; the first MTM values it at entry instead of the persisted last mark. This can make the post-restart portfolio equity disagree with the risk snapshot saved in the same backup.

## Test-first acceptance

- Save one open position with a non-entry last mark and a risk snapshot consistent with its marked PnL.
- Restore through `PlanBStatePersistence` and `UnifiedQuantEngine`.
- Assert the last mark is restored and `_unrealized_pnl_at_marks()` reproduces the saved marked equity before a fresh candle arrives.
- Reject a backup containing open positions but no corresponding mark map rather than silently substituting entry price.
- Validate finite positive marks and exact coverage for all open-position symbols.

## Proposed correction

Persist a validated `last_mark_prices` mapping for every open position. Restore it into the engine's `_last_mark_prices`; do not treat entry price as a valid substitute for a missing mark in an open-position recovery snapshot. Keep pending-only/cold-start backups valid.

No market backtest, parameter optimization, private API request or live order. No profitability claim.
