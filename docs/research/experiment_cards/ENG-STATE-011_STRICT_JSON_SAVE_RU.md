# ENG-STATE-011 — reject non-finite values during backup save

Статус до изменения: CONFIRMED PERSISTENCE DEFECT / JSON encoder emits NaN/Infinity by default.  
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
