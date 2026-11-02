# ENG-STATE-013 — validate backup metadata

Статус: ACCEPT — metadata validation regression и CI прошли.  
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

Решение: ACCEPT для локальной проверки envelope metadata.

- Engine commit: `b25fde3ceb8032cac45a879622d192335979b6cb`.
- Test commit: `f110f776a06bdde6aa7faa25b0e97a1601a6f989`.
- CI: [Research engine checks #41445058006](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41445058006), SUCCESS.
- `tests/test_state_persistence.py`: 40/40; valid writer output restores; malformed, naive and non-UTC timestamps and empty version rejected.
- Compile, configured deterministic suites and secret scan passed.

No market backtest, parameter sweep, production deployment or live order. Timestamp validation does not impose a freshness limit or reconcile state with Bybit.
