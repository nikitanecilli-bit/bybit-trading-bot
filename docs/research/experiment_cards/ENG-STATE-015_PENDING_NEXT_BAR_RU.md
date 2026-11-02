# ENG-STATE-015 — pending signal next-bar chronology

Статус до изменения: CONFIRMED LIFECYCLE GAP / a restored pending signal can be executed on an arbitrary later candle.  
Дата: 2026-11-02.  
Тип: pending-order lifecycle and restore validation; deterministic tests only.

## Наблюдаемая проблема

The engine documents pending signals as next-candle-only, and the strategy emits `signal_ts` as the signal candle OPEN timestamp. However:
- restore does not require or validate `signal_ts`;
- `_try_fill_pending` does not compare the execution candle timestamp with the signal candle timestamp.

After restart or a data gap, a pending signal can therefore be filled several candles late, violating the one-next-bar policy and changing entry price/execution semantics.

## Решение

- Require a positive integer `signal_ts` in pending backup entries.
- At fill time, require `curr.ts == signal_ts + timeframe_ms`; otherwise discard the pending signal without opening a position.
- Use the configured timeframe's candle-open timestamps. Do not infer elapsed wall-clock time.
- Reject malformed timestamps and unknown pending fields during restore.

## Критерии проверки

1. Valid next-bar pending signal remains eligible.
2. Stale/gapped pending signal is discarded and not filled.
3. Signal timestamp missing, malformed or non-positive is rejected on restore.
4. Unknown pending field is rejected.
5. Full deterministic CI passes.

No market backtest required.
