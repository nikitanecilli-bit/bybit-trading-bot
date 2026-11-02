# ENG-STATE-014 — TP1 timestamp consistency

Статус: ACCEPT — TP1 timestamp regression и CI прошли.  
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

Решение: ACCEPT для хронологии локального состояния позиции.

- Engine commit: `adc68a7c413abe5f642a10cd91348c81d15ea746`.
- Test commit: `e128b6865e290a9b597e4c1749d1fbeb99efd188`.
- CI: [Research engine checks #41445386482](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41445386482), SUCCESS.
- `tests/test_state_persistence.py`: 43/43; TP1 timestamp required iff TP1 hit and must not predate entry.
- Compile, configured deterministic suites and secret scan passed.

No market backtest, parameter sweep, production deployment or live order.
