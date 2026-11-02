# ENG-FUND-003 — defer ambiguous funding receipts during pre-exit MTM

Статус: PREREGISTERED — test-first; implementation pending.
Дата: 2026-11-02.
Тип: deterministic portfolio-risk accounting.

## Confirmed event order in the engine

`step_candle()` computes an adverse intrabar mark and calls `_update_mark_to_market(bar_close_ts)` before `_manage_position()` determines whether the candle stopped or fully closed the position. Funding settlements at that same close timestamp are included by `accrued_funding_cost()`.

Therefore a funding receipt can increase pre-exit MTM equity before the engine has resolved a stop/TP exit on that candle. It can partially offset the adverse mark and potentially delay a daily-stop/kill-switch decision. ENG-FUND-002 fixes realized PnL at final close but does not remove this pre-exit MTM optimism.

## Preregistered policy

For portfolio MTM only, do not credit a negative funding cost (receipt) when its settlement timestamp equals the current `as_of_ts` boundary. Continue charging positive funding costs (payments) in full. If the position remains open, the receipt becomes eligible on the next MTM timestamp because the settlement is then strictly earlier than `as_of_ts`. If the position closes at the boundary, ENG-FUND-002 keeps the receipt excluded permanently.

This delays uncertain receipts by one bar but does not delay payments. It avoids reordering stop/kill-switch/TP logic and avoids crediting income before same-boundary exit ordering is known.

## Tests

- Open long receiving funding: boundary MTM excludes receipt; next timestamp includes it.
- Open short receiving funding: same.
- Long/short funding payments remain charged at the boundary.
- TP1 partial state: receipt is deferred at exact as-of boundary, then included on later timestamp at remaining fraction.
- Existing funding realized PnL, MTM, coverage preflight, portfolio and execution tests remain green.

## Scope

No market backtest, parameter optimization, strategy change, private API request or live order. If the test reveals that current MTM/exit lifecycle cannot safely express this policy, stop and document rather than silently reorder event processing.
