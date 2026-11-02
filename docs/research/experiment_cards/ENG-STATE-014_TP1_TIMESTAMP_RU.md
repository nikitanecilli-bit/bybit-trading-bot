# ENG-STATE-014 — TP1 timestamp consistency

Статус до изменения: CONFIRMED VALIDATION GAP / partial TP1 state can omit or contradict its event timestamp.  
Дата: 2026-11-02.  
Тип: restored position event chronology; deterministic tests only.

## Наблюдаемая проблема

The restore validator checks `tp1_ts_ms` type when present, but does not tie it to `tp1_hit` or `entry_ts`. A position may restore as partially closed without a TP1 event timestamp, or carry a TP1 timestamp before entry / while TP1 is marked untouched.

## Решение

Require:
- if `tp1_hit=true`, `tp1_ts_ms` must be a positive integer and not earlier than `entry_ts`;
- if `tp1_hit=false`, `tp1_ts_ms` must be null/absent.

Do not compare TP1 time to backup save time here; timestamp freshness and exchange reconciliation are separate gates.

## Критерии проверки

1. Valid partial TP1 position round-trips.
2. TP1 hit without timestamp rejected.
3. TP1 timestamp before entry rejected.
4. TP1 timestamp with tp1_hit=false rejected.
5. Failed restore remains transactional.
6. Full deterministic CI passes.

No market backtest required.
