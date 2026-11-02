# ENG-STATE-007 — validate restored open-position schema

Статус: ACCEPT — open-position schema regression и CI прошли.  
Дата: 2026-11-02.  
Тип: state restore validation; deterministic tests only.

## Наблюдаемая проблема

`OpenPositionState(**...)` accepts many invalid values because dataclass type annotations are not runtime validation. The loader also silently discards unknown fields. A backup can therefore restore a position with string/NaN prices, invalid direction/order type, negative size, or unknown fields dropped; failures may occur later in PnL/position management.

## Решение

Validate restored position payload before constructing/committing:
- reject unknown fields rather than silently dropping them;
- require core fields (trade_id, symbol, direction, strategy, entry_ts, entry/stop/TP prices, initial_stop_dist, size_usdt, risk_usdt, order_type);
- require non-empty string IDs/symbol/strategy, long/short direction, market/limit order type;
- require positive finite prices/distances/notional/risk; integer positive entry timestamp;
- validate optional numeric fields and fractions, booleans and nonnegative bars-held.

Keep valid current and legacy payloads that omit optional fields compatible with dataclass defaults.

## Критерии проверки

1. Current valid position round-trips unchanged.
2. Unknown field rejected.
3. Invalid direction/order type rejected.
4. NaN/invalid numeric or negative quantity rejected.
5. Failed restore leaves risk manager unchanged.
6. Full CI passes.


## Результат

- Engine: `3a5fc1bdb6df645f9dc010f2f8abefaac918b82d`.
- Tests: `c76ad2ed897bc05b7e59be5deff66ba74418aa9c`.
- CI: [Research engine checks #41434308834](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41434308834), SUCCESS.
- `tests/test_state_persistence.py`: 18/18; unknown field, invalid direction, NaN price and negative notional rejected; failed restore leaves risk manager unchanged. Existing valid position round-trip passes.
- Compile, all configured deterministic suites and secret scan passed.

Решение: ACCEPT. Local state validation only; no exchange reconciliation, market backtest or live order.
