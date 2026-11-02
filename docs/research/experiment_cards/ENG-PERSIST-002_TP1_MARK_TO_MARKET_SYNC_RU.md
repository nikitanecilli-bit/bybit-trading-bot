# ENG-PERSIST-002 — synchronize portfolio MTM after TP1 state transition

Статус: PREREGISTERED — test-first reproduction pending.
Дата: 2026-11-02.
Тип: portfolio accounting / risk-state synchronization.

## Наблюдение

`step_candle()` updates portfolio MTM before `_manage_position()`. `_manage_position()` may then apply TP1, changing `realized_tp1_gross_usdt`, `remaining_fraction`, and the modeled exit-cost legs, but when the position remains open it does not recalculate portfolio MTM or persist the updated position. As a result, the persisted risk snapshot and `risk_mgr.unrealized_pnl/current_equity` can describe the pre-TP1 state while the open position already has post-TP1 state.

## Hypothesis to prove

On a candle where TP1 is reached but TP2/stop/time-stop are not, the engine leaves `risk_mgr.unrealized_pnl` inconsistent with `_unrealized_pnl_at_marks()` after `_manage_position()`. A crash before another persistence event can also restore an open position with `tp1_hit=True` while the saved equity snapshot reflects pre-TP1 accounting.

## Test-first acceptance

- Initialize one open long position and synchronized adverse intrabar mark.
- Run pre-management MTM, then `_manage_position()` on a candle that touches TP1 but not TP2/stop.
- Assert TP1 state is applied and `risk_mgr.unrealized_pnl == _unrealized_pnl_at_marks(exit_ts)`; assert current equity equals realized plus updated unrealized.
- Assert updated TP1 state and risk snapshot are persisted before returning from the candle lifecycle.

## Proposed correction

After a surviving TP1 transition, recalculate portfolio MTM at the same bar-close timestamp and persist the changed position/risk snapshot. Preserve funding boundary policy (receipt deferred at exact MTM boundary, payment charged) and avoid duplicate persistence if the position closes on the same candle.

No market backtest or live order until test-first and full CI acceptance. No profitability claim.
