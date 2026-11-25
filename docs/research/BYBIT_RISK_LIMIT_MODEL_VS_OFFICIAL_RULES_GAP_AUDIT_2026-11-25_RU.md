# Bybit Risk-Limit Model vs Official Rules — Gap Audit

**Review date:** 2026-11-25  
**Scope:** static audit of the research/backtest engine against Bybit's public risk-limit rules and V5 public API schema. No market/account API request, order, PnL run or backtest was performed for this audit.

## 1. Official Bybit mechanics verified

Primary sources:
- Risk Limit (Perpetual and Expiry Contracts), last updated 2026-09-04: https://www.bybit.com/en/help-center/article/Risk-Limit-Perpetual-and-Expiry-Contracts
- Maintenance Margin (USDT Perpetual and Expiry Contracts), last updated 2026-04-16: https://www.bybit.com/help-center/article/Maintenance-Margin-USDT-Contract
- V5 Get Risk Limit public endpoint: https://bybit-exchange.github.io/docs/v5/market/risk-limit
- V5 Get Instruments Info: https://bybit-exchange.github.io/docs/v5/market/instrument

Important rules:
1. Risk tiers are dynamic. As position value rises, maximum leverage can fall and IMR/MMR can rise.
2. Bybit's effective position value is side-specific:
   - One-way: `max(long open position value + long order value, short open position value + short order value)`.
   - Hedge mode: the same max-of-long-side-vs-short-side rule.
3. For USDT/USDC contracts, position value and order value are calculated using contract size × Mark Price.
4. Reduce-only and Close-on-Trigger orders are excluded from effective risk-limit value.
5. Once either side reaches its risk-limit cap, only Reduce-only and Close-on-Trigger orders are accepted; orders that increase effective value are rejected.
6. Mark Price changes can move a position into another tier in real time.
7. Risk parameter changes can affect IMR, MMR, maximum leverage and position limit. If a change cannot safely apply, Bybit documents a 10-day buffer during which only reduce-only orders/cancellations are allowed for the affected pair; the new parameters apply after the buffer.
8. Public GET `/v5/market/risk-limit` returns tier rows with `riskLimitValue`, `maintenanceMargin`, `initialMargin`, `maxLeverage` and `mmDeduction`. This is a current public snapshot endpoint, not a historical archive.

## 2. What the current research engine already implements

Relevant files:
- `bybit_risk_tiers.py`
- `mark_price_liquidation.py`
- `Bybit_Trading_Engine_v14_research.py`
- `bybit_market_state.py`

Existing foundations:
- Decimal-based risk-tier parsing and point-in-time snapshot selection.
- Dated tier snapshots can be joined with dated instrument specifications.
- Entry sizing can reject missing/stale tier data, position value above the highest tier, or leverage above the selected tier's maximum.
- Initial margin and maintenance margin are calculated from tier MMR, IMR, maximum leverage and maintenance-margin deduction.
- Mark-Price maintenance margin can re-select a tier using the current Mark Price for one isolated position.
- Liquidation-aware replay requires dated risk-tier history and Mark Price history; it does not silently substitute current or proxy values.
- The liquidation module explicitly states that it is not an account-level cross/portfolio margin or liquidation model and does not aggregate other positions or active orders.

## 3. Material gaps against the official risk-limit rules

### G1 — effective position value is not aggregated

The engine currently calls `calculate_margin_requirements_from_tiers` with the proposed single entry's notional (`size_usdt`) or the single position's Mark-Price notional. It does not calculate Bybit's effective position value as the maximum of the long-side and short-side totals, including all open orders.

Impact: in a scenario with an existing position plus one or more additional active orders, the selected tier can be understated. The simulator currently does not model a full exchange order book per symbol, so it cannot claim this rule is fully reproduced.

### G2 — active-order classification is incomplete

The simulator has pending entry signals, but not a complete set of exchange-active orders with side, remaining quantity, Mark-Price notional, Reduce-only and Close-on-Trigger flags.

Impact: it cannot faithfully distinguish orders that count toward the risk-limit value from protective orders that Bybit excludes.

### G3 — cap enforcement is not a full exchange rule

The engine rejects a proposed position if its individual notional exceeds the highest available tier and applies leverage/tier constraints to the proposed entry. It does not yet block an order because the combined side-specific effective position value (positions + active orders) would reach/exceed the exchange risk-limit cap.

### G4 — risk-parameter change buffer is not simulated

The announcement inventory now contains dated risk-limit events and some stated buffer end times, but the engine does not model the 10-day exchange restriction lifecycle:
- announcement publication time;
- new parameter effective time;
- buffer period;
- temporary Reduce-only/cancel-only restriction;
- automatic application after the buffer;
- early termination of the buffer where Bybit reserves that right.

The event inventory is partial and does not provide complete tier ladders, so this must remain unimplemented/fail-closed until adequate historical evidence exists.

### G5 — isolated position model is not account-level cross/portfolio margin

The existing liquidation module is explicitly position-level isolated margin. It does not reproduce cross-margin equity across multiple positions, portfolio margin stress testing, account-wide maintenance-margin ratio, insurance-fund/ADL mechanics, or exchange liquidation laddering.

## 4. Recommended implementation sequence

1. Add a pure, independently tested function for Bybit effective position value:
   - group non-reduce-only/non-close-on-trigger open positions and orders by long/short side;
   - calculate each component using contract quantity × Mark Price for USDT/USDC linear contracts;
   - return the maximum side total;
   - reject unknown order side/status/flags rather than treating unknown as zero.
2. Add an explicit per-symbol simulated order ledger with remaining quantity, side, order status and Reduce-only/Close-on-Trigger flags. Pending strategy signals alone are not enough.
3. Before accepting a new order, recompute effective position value including the proposed order and current Mark Price; block if the selected risk tier/cap would be exceeded.
4. Recompute the tier as Mark Price moves; preserve the distinction between entry leverage validation and ongoing MMR recalculation.
5. Add a dated risk-parameter event state machine for effective/buffer times only after complete historical tier data is available. Missing events or tier data must produce UNKNOWN / rejected, not a guessed state.
6. Keep cross/portfolio margin outside the isolated model until a separate account-level model and required evidence are available.

## 5. Acceptance decision

**Risk-tier calculation: PARTIAL FOUNDATION EXISTS.**  
**Bybit effective position value / active-order aggregation: NOT IMPLEMENTED.**  
**Risk-limit cap enforcement across aggregate positions and orders: NOT IMPLEMENTED.**  
**10-day parameter-change buffer lifecycle: NOT IMPLEMENTED.**  
**Cross/portfolio account-level margin: OUT OF SCOPE / NOT IMPLEMENTED.**

Do not describe the current engine as a complete Bybit risk manager or live-ready. It is a research/backtest simulator with useful tier-aware single-position components. No live execution capability is implied.
