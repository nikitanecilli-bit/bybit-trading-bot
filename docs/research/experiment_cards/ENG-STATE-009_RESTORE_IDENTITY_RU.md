# ENG-STATE-009 — reject contradictory restored symbol/order identities

Статус: ACCEPT — cross-object identity validation and CI passed.  
Дата: 2026-11-02.  
Тип: restore cross-object validation; deterministic tests only.

## Наблюдаемая проблема

The backup stores open positions and pending signals in separate symbol-keyed dictionaries. A corrupted backup can contain the same symbol in both. Engine processing prioritizes the open position and will not consume the pending signal, leaving stale conflicting state. Distinct open positions can also carry the same trade_id, breaking unique trade identity and journal attribution.

## Решение

Before commit:
- reject any symbol present in both open_positions and pending_orders;
- reject duplicate trade_id values across restored open positions.

No strategy, order, or PnL behavior changes.

## Критерии проверки

1. Existing valid restore unchanged.
2. Same symbol in open and pending rejected.
3. Duplicate trade_id across two positions rejected.
4. Failed restore leaves caller risk manager unchanged.
5. Full deterministic CI passes.

No market backtest required.

## Результат

- Engine commit: `984e6a085f74139299ae92c6dfc454686cc2a9a9`.
- Test commit: `c8b0ae1c34768e89a9948fb9352c040bff315d0c`.
- CI: [Research engine checks #41436083033](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41436083033), SUCCESS.
- `tests/test_state_persistence.py`: 31/31; overlap between open/pending symbol and duplicate trade IDs are rejected; failed restore leaves risk manager unchanged.
- Full configured deterministic suites, compile and secret scan passed.
- Decision: ACCEPT for local restore identity validation. No market backtest or live order.
