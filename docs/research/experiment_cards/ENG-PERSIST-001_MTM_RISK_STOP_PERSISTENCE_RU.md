# ENG-PERSIST-001 — persist portfolio risk-stop transitions immediately

Статус: PREREGISTERED — implementation not yet accepted.
Дата: 2026-11-02.
Тип: fail-safe state persistence / portfolio risk controls.

## Наблюдение

`_update_mark_to_market(ts_ms)` updates realized/unrealized equity and can set `daily_stop_triggered` or `kill_switch_triggered`, but the method itself does not persist state. In the current engine, `_persist()` is called on entries, pending-order changes and trade closes. An open position can trigger the daily stop on MTM without closing on that candle; if the process restarts before another persistence event, the backup may still contain the old risk flags.

## Hypothesis to prove

A process interruption after an MTM-triggered daily stop but before a close/entry persistence event can restore a stale backup with `daily_stop_triggered=false`, allowing new entries after restart. A similar gap may exist for kill-switch transition when the currently stepped symbol has no position and other positions have not yet been processed.

## Preregistered test-first change

- Build a deterministic engine fixture with persistence spy and controlled MTM PnL.
- Trigger daily stop from `_update_mark_to_market()` without a trade close; assert that persistence is called and the saved risk snapshot contains the stop flag.
- Trigger kill-switch from MTM without a close on the current symbol; assert the flag is persisted immediately.
- Run existing portfolio accounting and state-persistence suites unchanged.

## Proposed minimal correction

Persist immediately when either protective latch transitions from false to true during MTM. Avoid unconditional fsync on every candle. Do not change stop thresholds, exit sequencing, PnL calculation or strategy behavior.

## Acceptance

Accept only if tests fail before the fix, pass after it, and full Research CI passes. No market backtest, parameter search, private API request or live order.
