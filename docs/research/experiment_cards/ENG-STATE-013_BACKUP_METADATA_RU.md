# ENG-STATE-013 — validate backup metadata

Статус до изменения: CONFIRMED VALIDATION GAP / saved_at_utc and bot_version are written but ignored during restore.  
Дата: 2026-11-02.  
Тип: backup envelope metadata validation; deterministic tests only.

## Наблюдаемая проблема

The writer always emits `saved_at_utc` and `bot_version`, but the loader currently ignores both. A backup with malformed/missing metadata is indistinguishable from a current backup in diagnostics, weakening later freshness and migration controls.

## Решение

Require both metadata fields in the backup envelope:
- `saved_at_utc`: non-empty ISO-8601 string with explicit UTC offset equal to zero;
- `bot_version`: non-empty string.

Do not enforce an age/freshness threshold in this change. A valid timestamp does not prove that backup state matches current Bybit positions/orders.

## Критерии проверки

1. Current writer output restores.
2. Missing metadata rejected.
3. Invalid timestamp / timestamp without timezone / non-UTC offset rejected.
4. Empty bot version rejected.
5. Failed restore remains transactional.
6. Full deterministic CI passes.

No market backtest required.
