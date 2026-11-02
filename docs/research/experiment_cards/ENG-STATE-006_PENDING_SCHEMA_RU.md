# ENG-STATE-006 — validate restored pending signal schema

Статус: ACCEPT — pending schema regression и CI прошли.  
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

Validating local pending data does not reconcile it with exchange active orders. Решение: ACCEPT для локального state restore.

- Validator commit: `c76ad2ed897bc05b7e59be5deff66ba74418aa9c`.
- CI: [Research engine checks #41434308834](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41434308834), SUCCESS.
- `tests/test_state_persistence.py`: 18/18; валидный pending round-trip сохранён, malformed entry, missing field, invalid direction/order type, NaN и отрицательная цена отклоняются.
- Compile, все configured deterministic suites и secret scan прошли.

No market backtest or parameter sweep. Local pending validation still does not prove that the signal corresponds to an active exchange order.


## Результат

- Исправление и тесты: [CI #41433992368](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41433992368), SUCCESS.
- Engine commit: `f7ecec11e571c26cce4be2d01903a4d104b7f223`; пустые/нулевые malformed pending containers дополнительно отклоняются commit `990bcf9e66551edb0369e4f2c606e643b3e2ac5f`.
- Test commit: `b1eeede0558eec4125c7dd4be9bb8b80153bda0f`.
- State persistence tests: 14/14; valid pending signal round-trips, malformed entry/missing field/invalid direction/order type/NaN price are rejected; failed restore leaves risk manager unchanged.
- Compile, all configured deterministic tests and secret scan passed.

Решение: ACCEPT. No market backtest or live order. Local pending validation still does not reconcile pending signals with exchange active orders.
