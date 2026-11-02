# ENG-STATE-009 — risk snapshot cross-field invariants

Статус до изменения: CONFIRMED VALIDATION GAP / individually valid risk fields can describe impossible equity state.  
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

No market backtest required.
