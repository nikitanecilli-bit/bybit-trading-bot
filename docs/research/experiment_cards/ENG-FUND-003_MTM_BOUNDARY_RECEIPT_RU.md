# ENG-FUND-003 — funding receipt at pre-exit MTM boundary

Статус: ACCEPT — deterministic regression tests and full Research CI passed.
Дата: 2026-11-02.
Тип: accounting / portfolio-risk correctness; no market experiment.

## Confirmed lifecycle issue

In `step_candle()`, the engine computes adverse intrabar marks and calls `_update_mark_to_market(bar_close_ts)` before `_manage_position()` resolves stop/TP outcomes for that candle. A funding settlement can have the same timestamp as this MTM boundary. OHLC data cannot establish whether settlement occurred before or after the intrabar exit.

If the settlement is a funding receipt, crediting it immediately can temporarily increase equity before the engine resolves a same-boundary stop/exit. That optimistic amount can offset an adverse mark during daily-stop / kill-switch evaluation.

## Conservative policy

- At an exact current MTM boundary, defer receipts (negative funding cost) until the next mark.
- Continue charging payments (positive funding cost) at the boundary.
- If the position remains open, the receipt is recognized at the next mark using the exposure that remains then, including TP1-reduced quantity.
- If the position fully closes at that boundary, ENG-FUND-002 ensures no receipt is credited to the closed position.
- This policy avoids inventing intrabar event ordering from OHLC.

## Implementation

- `accrued_funding_cost()` accepts `defer_boundary_receipts=True`.
- Portfolio MTM invokes the helper with this flag.
- Strictly earlier settlements and payment handling remain unchanged.

## Regression coverage

- Long receipt deferred at current boundary, recognized at next mark.
- Short receipt deferred at current boundary.
- TP1 receipt deferred, then recognized only on remaining quantity.
- Payment remains charged at current boundary.
- ENG-FUND-002 separately covers full-close receipt/payment at the same boundary.

## Evidence

- Test-first regression was added before the implementation; the pre-fix behavior failed the new boundary expectation.
- Full Research CI [#41503287534](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41503287534) completed SUCCESS on commit `037aabd80769be88ea6ed99b05855665da92230d`.
- The job log confirms 27/27 gap-execution tests, 38/38 time-model tests, 5/5 timeframe tests, 16/16 portfolio-accounting tests and 54 persistence tests passed; funding MTM and other unittest suites also completed successfully.
- The workflow's 21 direct `python tests/test_*.py` invocations were audited: every referenced file has an executable `__main__` path; plain-function suites use explicit runners and unittest suites invoke `unittest.main()`.

## Scope and limitations

No market backtest, parameter search, private API request or live order. This accepts the conservative accounting/risk-boundary behavior only; it is not evidence of strategy profitability or Bybit fill realism.
