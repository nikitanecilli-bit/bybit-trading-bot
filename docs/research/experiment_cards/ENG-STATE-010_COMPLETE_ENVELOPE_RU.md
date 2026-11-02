# ENG-STATE-010 — require complete persisted state envelope

Статус до изменения: CONFIRMED SAFETY GAP / valid JSON can omit portfolio fields and silently restore defaults.  
Дата: 2026-11-02.  
Тип: backup envelope validation; deterministic tests only.

## Наблюдаемая проблема

`load_state()` uses `data.get(..., {})` and defaults missing root fields. A syntactically valid but incomplete backup such as `{"risk": {...}}` can be accepted as an empty portfolio, silently dropping open positions or pending signals. Missing risk flags can also reset protective state to defaults.

The current writer always emits risk, open_positions, pending_orders and trade_seq, and the risk snapshot includes the full known risk schema.

## Решение

Require all persisted envelope keys: `risk`, `open_positions`, `pending_orders`, `trade_seq`. Require all known risk keys emitted by `AdaptiveRiskManager.to_dict()`; reject unknown or missing fields. No silent empty defaults for an existing backup.

Do not change backup writer format or strategy behavior.

## Критерии проверки

1. Current writer round-trip remains valid.
2. Missing each required root field rejected.
3. Missing risk flag/equity field rejected.
4. Failed restore remains transactional.
5. Full deterministic CI passes.

No market backtest required.
