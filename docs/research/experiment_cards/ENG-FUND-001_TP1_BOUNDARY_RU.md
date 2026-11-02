# ENG-FUND-001 — conservative funding when settlement shares TP1 boundary

Статус: PREREGISTERED — pending regression test and CI.
Дата: 2026-11-02.
Тип: deterministic funding-accounting correctness; не рыночный эксперимент.

## Наблюдаемое поведение

`funding_accounting.accrued_funding_cost()` currently applies full initial quantity to every funding settlement with `ts <= tp1_ts_ms`, and applies `remaining_fraction` only to settlements strictly after TP1 timestamp.

The TP1 timestamp is the candle-close boundary used by the OHLC simulator. A funding settlement can share that exact timestamp. OHLC data does not establish whether the partial TP1 exit occurred before or after settlement inside that boundary.

## Гипотеза дефекта

Always choosing full initial quantity at the shared timestamp is not conservative for every funding sign/direction:
- when the signed funding cashflow is a payment (positive cost), full quantity is the conservative case;
- when it is a receipt (negative cost), full quantity maximizes credited income and can overstate equity; remaining quantity is the conservative case.

This affects only funding events exactly at `tp1_ts_ms`. Events strictly before TP1 remain full quantity; events strictly after remain remaining quantity.

## Preregistered correction

At the shared timestamp, compute signed funding cost for the full initial quantity:
- if positive, use full quantity;
- if negative, use remaining fraction;
- if zero, either choice is identical.

This selects the less favorable PnL outcome under the unresolved intrabar event ordering. Do not change treatment of other timestamps.

## Tests required

- Long, positive funding rate at TP1 boundary: full-quantity payment remains.
- Long, negative funding rate at TP1 boundary: receipt is reduced to remaining quantity.
- Short, positive funding rate at TP1 boundary: receipt is reduced to remaining quantity.
- Short, negative funding rate at TP1 boundary: full-quantity payment remains.
- Existing before/after TP1, missing mark, duplicate event, invalid position and zero remaining tests remain green.

## Scope and limitations

- No strategy change, no parameter optimization and no market backtest.
- This is a conservative ambiguity policy for an OHLC simulator, not a claim about actual Bybit event ordering.
- Exact exchange settlement quantity still requires authoritative exchange execution/position data.
