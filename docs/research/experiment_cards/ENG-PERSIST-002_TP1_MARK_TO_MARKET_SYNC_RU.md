# ENG-PERSIST-002 — synchronize portfolio MTM after TP1 state transition

Статус: ACCEPT — test-first reproduction and full Research CI passed.
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


## Реализация и результат

- Test-first commit: `3888dbee467aaec71764209610a4f73412baba56`.
- Full Research CI [#41506138601](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41506138601) failed exactly at the new assertion that MTM unrealized PnL must match the post-TP1 position state. Traceback: `test_tp1_transition_refreshes_and_persists_portfolio_mtm`, line 400.
- Fix commit: `7734fecaee62d84dd40039c36e2b0fede0386387`. After surviving TP1 transition, the engine recalculates MTM at the same close timestamp; it persists each surviving open position after candle management so bars-held, MFE/MAE and protective trailing-stop evolution survive restart. Closed positions continue to use `_close_position()` persistence.
- Gap-execution tests initially exposed an outdated `RiskSpy` fixture without MTM support; the fixture was updated, not the production code weakened.
- Full Research CI [#41506990147](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41506990147) completed SUCCESS on commit `300af4a35ba7c3cb30d75a66e99eeb349ba7a44d`. Logs confirm the new TP1 sync test, surviving-position persistence test, and same-bar TP1/stop order-independence test all passed; portfolio suite 21/21.
- Decision: ACCEPT for TP1/MTM consistency and persistence of open-position lifecycle state. No market backtest or live order; no profitability claim.


## Дополнительная проверка одновременных выходов

- Added same-timestamp cross-symbol replay: TP1 on BTCUSDT + stop on ETHUSDT is invariant to symbol iteration order; realized/unrealized/current equity reconcile in both permutations.
- Added simultaneous two-symbol stop-close test: both trade records are written exactly once, realized equity equals opening equity plus the sum of both net trade PnLs, unrealized PnL is zero, and final equity is order-independent.
- Full Research CI [#41507219610](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41507219610) SUCCESS on test commit `4e08f7387c970941797aa1c4d1342ef56301c2a0`; portfolio suite 22/22 and state-persistence suite 54 tests passed.
