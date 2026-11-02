# ENG-STATE-016 — backup event timestamps bounded by save time

Статус: ACCEPT — backup event chronology regression и CI прошли.  
Дата: 2026-11-02.  
Тип: backup envelope and event chronology; deterministic tests only.

## Наблюдаемая проблема

The loader validates that `saved_at_utc` is a UTC timestamp and that entry/TP1/pending timestamps are positive, but does not verify that those events occurred on or before the backup's save time. A malformed or clock-skewed backup can therefore claim a future entry, TP1, or pending signal.

## Решение

Convert the validated UTC save timestamp to milliseconds and require:
- every restored position `entry_ts <= saved_at_utc`;
- every non-null `tp1_ts_ms <= saved_at_utc`;
- every restored pending `signal_ts <= saved_at_utc`.

Keep backup age/freshness threshold separate. A backup may be internally chronological yet stale relative to Bybit.

## Критерии проверки

1. Existing valid round-trip and partial TP1 restore remain valid.
2. Future entry timestamp rejected.
3. Future TP1 timestamp rejected.
4. Future pending signal timestamp rejected.
5. Failed restore remains transactional.
6. Full deterministic CI passes.

Решение: ACCEPT для внутренней хронологии резервной копии.

- Engine commit: `8b33bd56c73c7abaf43513b59d16f6c5295bc8fb`.
- Test commit: `ab74e2918f3c897443f0b0d1acbbfd7059fa9528`.
- CI: [Research engine checks #41447112303](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41447112303), SUCCESS.
- `tests/test_state_persistence.py`: 51/51; future entry, TP1 and pending timestamps rejected.
- Compile, configured deterministic suites and secret scan passed.

No market backtest, parameter sweep, production deployment or live order.

