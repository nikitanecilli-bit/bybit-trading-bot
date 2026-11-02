# ENG-STATE-009 — reject contradictory restored symbol/order identities

Статус до изменения: CONFIRMED STATE INTEGRITY GAP.  
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
