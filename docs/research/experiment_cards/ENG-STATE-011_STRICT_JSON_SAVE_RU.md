# ENG-STATE-011 — reject non-finite values during backup save

Статус: ACCEPT — strict JSON serialization and CI passed.  
Дата: 2026-11-02.  
Тип: fail-closed serialization; deterministic tests only.

## Наблюдаемая проблема

Python's `json.dump()` defaults to `allow_nan=True`, writing non-standard JSON tokens `NaN` / `Infinity`. The save path can therefore report success and atomically replace the last good backup with a file that the stricter restore validator later rejects.

## Решение

Serialize with `allow_nan=False`. On non-finite values, preserve the previous backup, remove the failed temp file best-effort and raise the existing fail-closed RuntimeError.

## Критерии проверки

1. Normal backup save/restore unchanged.
2. NaN/Infinity in persisted risk or position data causes save failure.
3. Existing good backup remains unchanged.
4. Failed temp file is removed.
5. Full deterministic CI passes.

No market backtest required.

## Результат

- Engine commit: `1a354260945ed34a0be466d790fa24254cd5d472`.
- Test commit: `87a483a4fd9a2a2518bc1ca3fcdc9c4df5301c70`.
- CI: [Research engine checks #41436653943](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41436653943), SUCCESS.
- `tests/test_state_persistence.py`: 35/35. NaN in risk and Infinity in position now fail save, preserve previous backup, and clean temp file.
- Compile, all configured deterministic suites and secret scan passed.
- Decision: ACCEPT. No market backtest or live order.
