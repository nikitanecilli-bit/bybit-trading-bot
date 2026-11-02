# ENG-STATE-008 — validate restored TP1 state invariants

Статус: ACCEPT — TP1 cross-field invariants and CI passed.  
Дата: 2026-11-02.  
Тип: restore invariant validation; deterministic tests only.

## Наблюдаемая проблема

ENG-STATE-007 validates each position field independently, but does not validate cross-field consistency. A backup can claim `tp1_hit=true` while `remaining_fraction=1.0`, or `tp1_hit=false` with a partially closed quantity / realized TP1 PnL. MTM and final close accounting use these fields independently, which can double-count or omit the TP1 leg.

Likewise, TP1/TP2 targets must be on the profitable side of entry and ordered by distance for the position direction.

## Решение

Reject restored positions unless:
- long: entry < TP1 < TP2; short: entry > TP1 > TP2;
- TP1 hit implies remaining_fraction equals 1 - TP1_FRACTION and TP1 realized gross PnL is non-negative;
- TP1 not hit implies remaining_fraction is 1 and realized TP1 gross PnL is zero (within small numeric tolerance).

Do not constrain current stop relative to entry: trailing logic may legitimately move it through breakeven.

## Критерии проверки

1. Current valid open and TP1-partial positions restore.
2. Contradictory TP1 flag/fraction rejected.
3. TP1 flag/realized PnL contradiction rejected.
4. Reversed or unordered targets rejected.
5. Failed restore remains transactional.
6. Full deterministic CI passes.

No market backtest required.

## Результат

- Engine commit: `22664bd79f8fc93c0cbf7dbafc5c775a82e8cde3`.
- Test correction commit: `529d1d725752a3010dedc3c06d1c48c572a1e15b`.
- CI: [Research engine checks #41435897233](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41435897233), SUCCESS.
- `tests/test_state_persistence.py`: 29/29. Valid TP1 partial position round-trips; inconsistent TP1 flags/fraction/PnL and unordered long/short targets fail closed.
- Full configured deterministic suites, compile and secret scan passed.
- Decision: ACCEPT for local state restore validation. No market backtest or live order.
