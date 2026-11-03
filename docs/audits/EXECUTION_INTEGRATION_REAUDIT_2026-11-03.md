# Execution integration re-audit — 2026-11-03

Branch: `research/market-regime-v1-main`  
Scope: current engine lifecycle, exchange sizing, risk tiers, Mark-Price liquidation, funding, state persistence, and H1 portfolio runner.  
Verification commit: `ab1679ef290612714aa265245954e58cc971b00c`  
Research CI: [#41651782655 — SUCCESS](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41651782655)

## Why this re-audit exists

Several earlier audit notes describe the engine before the latest integration work. In particular, the statements that exchange sizing is not wired into the engine and that liquidation is absent are now stale. This document supersedes those specific implementation-status statements; it does not remove the remaining execution-realism blockers below.

## Current implementation confirmed by source inspection

### 1. Exchange-valid entry sizing is wired

`UnifiedQuantEngine._try_fill_pending()` now:
- selects the dated instrument specification as of the entry candle;
- validates configured leverage against the instrument leverage filter;
- calls `size_to_exchange_constraints()`;
- rejects missing/stale specs, non-trading instruments, invalid lot sizes, min-notional violations and order-quantity caps without a notional-proxy fallback;
- stores exact initial and remaining contract quantity plus qty step and minimum order constraints on `OpenPositionState`.

TP1 quantity is floored to qtyStep. The engine skips TP1 when the split would violate minimum quantity/notional constraints. Final ordinary reduce quantity is checked again before the close is recorded.

### 2. Dated risk tiers are wired into entry sizing and liquidation health

When a risk-tier history is supplied, the entry path selects the as-of tier, enforces the tier leverage limit, and records tier ID, risk limit, MMR, mmDeduction, max leverage, initial margin and maintenance margin on the open position.

The H1 portfolio runner requires dated instrument-spec and risk-tier directories and checks their coverage per scored fold. A current-only snapshot cannot be applied retrospectively to an old fold.

### 3. Mark-Price liquidation path exists, but is a position-level isolated model

With risk-tier history and full Mark OHLC supplied, the engine:
- requires an exact-timestamp Mark OHLC candle for an open position;
- evaluates adverse Mark wick against dynamic mark-notional risk tiers;
- uses the stored entry leverage and remaining contract quantity;
- includes accrued funding in the remaining isolated-position margin health;
- gives a Mark-triggered liquidation precedence over a Last-Price stop in the same OHLC interval;
- books the modeled bankruptcy price for the liquidation takeover.

This is materially more complete than the former no-liquidation model, but it is **not** a full Bybit account engine. The implementation explicitly omits partial-liquidation ladder behavior, cross-margin/shared-collateral accounting, portfolio-margin stress, auto-add-margin behavior, manual extra-margin changes, and exact exchange liquidation rounding/settlement behavior.

**Account-mode blocker:** the config's `ISOLATED_5X` string does not prove whether the real account is Classic isolated or Unified Trading Account isolated. The current calculator is an isolated USDT position-level model; do not interpret it as account-verified Bybit liquidation fidelity until the actual account/product mode is confirmed. Cross and Portfolio Margin remain unsupported.

### 4. Funding uses exact contract quantity when present

Funding accounting now uses `contract_qty` and `remaining_contract_qty` when available, including the post-TP1 remaining quantity. Legacy notional-based quantity remains as a compatibility fallback for positions created before exchange sizing.

Funding still uses the open of the exact-timestamp Mark candle as a settlement-price proxy. That is not proof that the archived value equals Bybit's actual settlement mark for every funding event.

### 5. Closed trade journal now retains execution provenance

`TradeRecord` now carries:
- `exchange_sized`;
- initial `contract_qty`;
- `tp1_contract_qty`;
- `final_contract_qty` (remaining quantity on the final close leg);
- `qty_step`;
- leverage and selected risk-tier/margin fields.

The portfolio-accounting regression test asserts that an exchange-sized position's initial, TP1 and final quantities survive the transition from open position to closed trade. This closes a prior auditability gap; it does not replace an exchange execution ledger or reconciliation.

### 6. H1 runner output caveat corrected

The strict H1 runner now reports Bybit-native H1 trade OHLCV rather than the obsolete Binance-proxy caveat. It still states the remaining limitations: OHLC limit penetration is not queue execution, funding mark is a candle-open proxy, fees/slippage are fixed assumptions, and L2/spread/partial-fill adverse selection are not modelled.

## CI and regression repairs in this re-audit

The final Research CI run [#41651782655](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41651782655) completed SUCCESS on `ab1679ef290612714aa265245954e58cc971b00c`.

During the run, the following deterministic regressions were exposed and repaired:
- intrabar MTM/liquidation caches are initialized safely for restored or fixture-created engine objects that did not pass through `__init__`;
- time-model test positions now provide the direction/stop fields required by the newer intrabar risk-mark path;
- legacy Plan B positions with `leverage=null` can be restored, while exchange-sized positions must carry a positive leverage value;
- closed-trade execution provenance is asserted in the portfolio-accounting tests.

The final run passed the complete configured Research CI job, including instrument specs, risk tiers, isolated liquidation model, Mark OHLC integration, exchange sizing, funding accounting, time model, H1 execution gates, portfolio accounting, state persistence, relative strength, and secret scan.

## Remaining blockers — do not confuse green CI with live readiness

| Priority | Status | Blocker |
|---|---|---|
| P0 | BLOCKED | No committed dated Bybit instrument-spec and risk-tier snapshots with sufficient historical coverage |
| P0 | BLOCKED | No verified full Bybit H1 trade-kline, funding and Mark OHLC archive for the intended scored folds |
| P1 | BLOCKED | Actual account/product margin mode (UTA isolated vs Classic isolated) is not confirmed; Cross/Portfolio Margin are unsupported |
| P1 | OPEN | No historical bid/ask/L2 queue, partial-fill or adverse-selection model |
| P1 | OPEN | Funding uses timestamp-aligned Mark-candle open proxy, not separately verified settlement mark |
| P1 | OPEN | Fees/slippage are baseline constants, not the account's actual fee tier and symbol/time/size-specific execution costs |
| P2 | OPEN | Closed TradeRecord has quantity/tier provenance but not an exchange execution-ID/fill ledger; report-only exchange reconciliation is still a separate gate |
| P2 | OPEN | Point-in-time universe collector records current status/lifecycle bounds but does not prove historical temporary suspensions or complete historical delisting availability |

## Decision

- Do not repeat the old claim that exact quantity sizing and isolated liquidation are absent; they are now integrated.
- Do not claim full Bybit execution fidelity or live readiness.
- Do not run another strategy parameter sweep on CryptoFetch/Binance proxy data.
- Continue accumulating official Bybit snapshots and H1/funding/Mark history through an allowed runner/network route.
- Before interpreting liquidation results, explicitly confirm the account/product margin mode and configure a matching model.
- Once the data gates are met, run one frozen-strategy execution-aware validation; keep maker fills as an optimistic upper bound until order-book/queue data is available.

## Related notes that need future reconciliation

- `docs/audits/EXCHANGE_SIZING_INTEGRATION_AND_BYBIT_SCHEMA_2026-11-03.md`
- `docs/audits/LEVERAGE_MARGIN_LIQUIDATION_AUDIT_2026-11-03.md`
- `docs/audits/EXECUTION_REALISM_READINESS_RU.md`

Their historical findings remain useful for chronology, but implementation-status statements preceding this re-audit must be read as superseded where they conflict with the current source described above.
## 2026-11-03 — H1 archive ingestion and cost-stress hardening

The strict H1 runner now rejects two malformed-but-regular archive cases before alignment or replay:

- Every Bybit H1 `timestamp_ms` must lie exactly on the UTC hour grid (`timestamp_ms % 3_600_000 == 0`), in addition to requiring a continuous one-hour interval. A uniformly shifted series can no longer pass merely because adjacent deltas are correct.
- Every CSV must contain a `symbol` column, and each row's symbol must match the uppercase filename stem. A mislabeled or cross-contaminated file cannot silently be replayed under another instrument's specs.

The runner's cost multiplier is also scoped to the replay with a context manager. Taker fee, maker fee and taker slippage globals are restored in a `finally` path after both successful and failed runs; invalid non-finite or non-positive multipliers are rejected. This prevents a prior stress variant from contaminating later baseline/variant runs in the same process.

Regression evidence: Research CI [#41678760487](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41678760487), commit `64efe9dae73b34be06f00fc108964811b260ee04`, SUCCESS. The H1 runner gate suite passed **15/15**, including off-hour timestamps, filename/row symbol mismatch, and cost-global restoration after success/exception. The complete configured Research CI job also passed.

Scope: input validation and research-run isolation only. No strategy parameters, signal rules, position sizing formulas, market PnL results, or live execution behavior were changed. The H1 runner still requires actual dated Bybit instrument/risk-tier snapshots, Bybit H1 trade candles, funding and Mark OHLC archives; the green CI does not create or validate the existence of those real archives.
