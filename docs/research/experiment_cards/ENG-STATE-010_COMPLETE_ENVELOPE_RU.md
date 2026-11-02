# ENG-STATE-010 — require complete persisted state envelope

Статус: ACCEPT — required envelope and risk snapshot validation passed CI.  
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

## Результат

- Engine commit: `e8171203ad3f87ad19bca064f9a32b4c8a4ec2f0`.
- Test fixture / coverage commit: `46c4f01a291634cc2b71f4227c41dfb0b0091e2f`.
- CI: [Research engine checks #41436427155](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41436427155), SUCCESS.
- `tests/test_state_persistence.py`: 33/33; all four envelope keys and protective risk flags are required. Tests for malformed positions, pending payloads, risk values and transactionality now use otherwise-valid complete snapshots, so they exercise their intended validation layer.
- Compile, configured deterministic suites and secret scan passed.
- Decision: ACCEPT for complete snapshot validation. Existing backup with missing fields now fails closed; explicit migration would be needed for older formats.
