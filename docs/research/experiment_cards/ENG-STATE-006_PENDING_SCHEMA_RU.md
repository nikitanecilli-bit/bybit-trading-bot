# ENG-STATE-006 — validate restored pending signal schema

Статус до изменения: CONFIRMED SAFETY DEFECT / nested pending payload is not validated.  
Дата: 2026-11-02.  
Тип: state restore validation; deterministic tests only.

## Наблюдаемая проблема

ENG-STATE-005 validates that `pending_orders` is a JSON object, but not its nested values. A backup such as `{"pending_orders":{"BTCUSDT":[]}}` passes restore and later crashes when portfolio ranking or fill logic calls `.get()` / indexes required signal fields. An invalid direction/order type can also enter the fill path.

## Решение

Validate every pending entry before commit:
- non-empty symbol key and object value;
- required signal fields: symbol, direction, strategy, entry_price, stop_dist, order_type;
- symbol matches key; direction is long/short; order_type market/limit;
- numeric fields are finite, entry_price and stop_dist positive;
- vol_ratio, if present, finite and non-negative.

Keep valid generated signal payloads unchanged. No strategy or fill behavior changes.

## Критерии проверки

1. Valid pending signal round-trips unchanged.
2. Non-object entry rejected.
3. Missing required field rejected.
4. Invalid direction/order type/numeric values rejected.
5. Failed restore leaves caller risk manager unchanged.
6. CI passes.

## Границы

Validating local pending data does not reconcile it with exchange active orders. Market backtests are not required.
