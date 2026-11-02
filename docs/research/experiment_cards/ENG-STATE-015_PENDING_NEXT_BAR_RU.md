# ENG-STATE-015 — pending signal next-bar chronology

Статус: ACCEPT — pending chronology regression и CI прошли.  
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

Решение: ACCEPT для сохранения one-next-bar execution semantics.

- Engine commits: `e62bdf2b78a89eacfcf13e52dd852bf19ad75f31`, `62249c6a3e2db534cb6841b6f639720ede334b46`.
- Test commits: `ac8039255622b574cd400a54a3bb9ab41624f205`, `43cb26751f60f968169d9d4b30cd406584ed6ba0`, `66d974f26ec8dedb48141dd6185908ad46ec9942`, `4af98d794c6fdb18b7d1277026bb5510edf8421b`.
- CI: [Research engine checks #41446661723](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41446661723), SUCCESS.
- `tests/test_state_persistence.py`: 48/48; `tests/test_gap_execution.py`, `tests/test_time_model.py` and configured deterministic suites passed.
- Compile and secret scan passed.

No market backtest, parameter sweep, production deployment or live order.
