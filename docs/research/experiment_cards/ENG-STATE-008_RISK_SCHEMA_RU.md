# ENG-STATE-008 — validate restored risk-manager schema

Статус: ACCEPT — risk schema validation regression и CI прошли.  
Дата: 2026-11-02.  
Тип: state restore risk validation; deterministic tests only.

## Наблюдаемая проблема

`AdaptiveRiskManager.from_dict()` directly casts numeric values to float and uses permissive `_as_bool()`. A syntactically valid backup can restore NaN/infinity into equity/drawdown, negative equity, malformed day strings or arbitrary values silently coerced to False. The loader currently stages this object, but staging alone does not validate its semantic integrity.

## Решение

Validate supplied risk fields before calling `from_dict()`:
- reject unknown keys;
- numeric fields must be finite numbers (bool excluded);
- realized/current/peak/day-start equity must be positive;
- max_drawdown_pct must be in [0, 100];
- current_day_str must be empty or ISO YYYY-MM-DD;
- risk flags must be actual booleans.
- Preserve optional legacy fields by allowing omitted keys and using existing defaults.

## Критерии проверки

1. Existing full risk round-trip remains valid.
2. NaN/infinite/negative equity rejected.
3. Invalid drawdown and day string rejected.
4. String/number flags rejected.
5. Failed restore leaves caller risk manager unchanged.
6. Full CI passes.

No market backtest required. Local validation does not reconcile with Bybit.


## Результат

- Engine commit: `84beee0dbe10cd0ab6f9e67255c21d6518a80957`.
- Tests commit: `4a9045fdc01f36c4b4a5e52278691056d4dce9ae`.
- CI: [Research engine checks #41434930478](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41434930478), SUCCESS.
- `tests/test_state_persistence.py`: 23/23; NaN/negative equity, out-of-range drawdown, malformed date/flag and unknown risk field rejected; failed restore leaves caller risk manager unchanged.
- Compile, all configured deterministic suites and secret scan passed.

Решение: ACCEPT. Local risk-state schema validation only; no exchange reconciliation, market backtest or live order.
