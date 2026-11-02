# ENG-STATE-012 — risk snapshot cross-field invariants

Статус: ACCEPT — risk snapshot invariants regression и CI прошли.  
Дата: 2026-11-02.  
Тип: risk snapshot restore validation; deterministic tests only.

## Наблюдаемая проблема

Risk restore validates field types and ranges separately, but does not verify accounting identities:
- current_equity must equal rounded realized_equity + unrealized_pnl;
- peak_equity must not be below current_equity;
- max_drawdown_pct must be at least the drawdown implied by current_equity vs peak_equity.

An inconsistent backup can therefore restore contradictory risk controls and equity state.

## Решение

Validate the three cross-field invariants before applying the staged risk state. Use the engine's existing four-decimal equity rounding and a small tolerance for percentage arithmetic. Keep legitimate historical max drawdown greater than current drawdown.

Update the valid round-trip fixture to include a consistent max_drawdown_pct.

## Критерии проверки

1. Valid risk snapshot round-trips.
2. Current equity mismatch rejected.
3. Peak below current equity rejected.
4. Reported max drawdown below implied drawdown rejected.
5. Historical max drawdown above current drawdown accepted.
6. Failed restore leaves caller risk manager unchanged.
7. Full deterministic CI passes.

Решение: ACCEPT для локального восстановления risk snapshot.

- Engine commit: `70b7b01fa6f549956e9be7ca19990e3724ee9416`.
- Test commit: `23b3aa3f4af24b5d4b45f9a79eec0cf0be4f225a`.
- CI: [Research engine checks #41444495022](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41444495022), SUCCESS.
- `tests/test_state_persistence.py`: 39/39; invalid accounting identities rejected, historical max drawdown above current drawdown accepted.
- Compile, configured deterministic suites and secret scan passed.

No market backtest, parameter sweep, production deployment or live order.
