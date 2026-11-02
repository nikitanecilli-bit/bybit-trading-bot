# ENG-PERSIST-003 — restore last known marks for open positions

Статус: ACCEPT — pre-fix CI reproduction and full post-fix Research CI passed.
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


## Реализация и доказательства

- Test-first CI [#41509292651](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41509292651) was run against the pre-fix engine source. The state-persistence step failed with six `TypeError: PlanBStatePersistence.save_state() got an unexpected keyword argument 'last_mark_prices'` errors, demonstrating that the old recovery contract had no persisted-mark support.
- Fix commit: `496cafecf0d5f622cd4480c635eec5b94a35184f`; restored on branch in `0824d623f5ea2112e3051c905f434cbe42c7500b`.
- `PlanBStatePersistence.save_state()` now requires a finite positive last mark for every open position and writes the exact symbol-to-price map. `load_state()` validates exact symbol coverage and finite positive values, and rejects open-position backups without marks. The engine's `_persist()` passes `_last_mark_prices`; restore hydrates `_last_mark_prices` before the first new candle.
- Full Research CI [#41509504557](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41509504557) completed SUCCESS; 58 state-persistence tests ran. Coverage includes engine restore preserving equity from the saved mark, rejection of missing marks, and rejection of zero/negative/NaN/Inf/boolean marks.
- The last mark is a recovery snapshot, not a live exchange quote. It does not replace Bybit reconciliation or guarantee freshness after downtime; live trading remains out of scope.


## Engine integration confirmation

- Added explicit `_persist()` integration test: an engine with an open BTCUSDT position and mark 103.25 writes that mark into the backup; a fresh `PlanBStatePersistence` instance restores it.
- Full Research CI [#41509795468](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41509795468) SUCCESS; state-persistence suite 59 tests passed, including the engine `_persist()` integration test.
