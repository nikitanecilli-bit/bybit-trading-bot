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


## 2026-11-03 — Funding allocation after partial TP1

The liquidation margin path previously charged 100% of pre-TP1 Funding settlements to the remaining position after a partial close. This was corrected: once TP1 is effective as of the margin timestamp, all historical funding cashflows are prorated to the exact remaining contract quantity (or legacy remaining fraction). Full trade-lifecycle Funding remains unchanged for closed PnL. Regression tests cover long payments, short receipts, exact quantity, as-of boundary, and the engine-to-liquidation call path. See `PORTFOLIO_ACCOUNTING_NET_R_MAE_MFE_AUDIT_2026-11-03.md`.

**Important remaining approximation:** Bybit's Funding Fee article says funding is deducted from available balance first; if available balance is insufficient, it is deducted from position initial margin, increasing isolated liquidation risk. The current position-level simulator applies net funding directly to isolated position margin without modelling the account's available-balance sufficiency. This can overstate liquidation risk when paid Funding could be covered by available balance, and can understate risk if received Funding is credited only to available balance rather than isolated position margin. The error direction depends on funding sign and account balance; it is not uniformly conservative. It is not a complete UTA account simulation.

The updated Funding accounting, realized Funding, and Mark OHLC liquidation integration test steps passed in CI run [#41715596303](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41715596303); overall workflow terminal status was still pending when this note was written.


### Exact entry/Funding timestamp boundary

The funding ledger now includes a Funding settlement whose timestamp exactly matches the modeled entry candle open using a conservative event-order rule: charge a possible payment, do not assume a possible receipt. Settlements strictly before entry remain excluded. This reflects Bybit's documented uncertainty for orders opened/closed within five seconds of settlement; the simulator does not have exchange fill timestamps precise enough to determine actual inclusion. CI [#41716240400](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41716240400) passed 50/50 steps, including realized Funding PnL and cumulative Funding accounting tests.


### Marketable TP limit gaps — 2026-11-03

A fee-classification asymmetry was confirmed in the execution model. Entry limit orders that are marketable at the next candle open are correctly reclassified as taker, but TP1/TP2 limit targets were previously charged at the configured maker rate even when the candle opened through the target. A resting sell limit for a long (or buy limit for a short) becomes marketable when the open is beyond its limit; the maker assumption was therefore optimistic on gap-through target legs.

**Correction:**
- TP1 liquidity classification is now stored per position as tp1_maker.
- A TP1 limit target opened through at the start of the candle is classified as taker and incurs taker fee plus modeled slippage; an ordinary intrabar touch retains the configured maker proxy.
- Final TP2 exit classification is calculated separately for the actual close bar and recorded as final_exit_maker.
- Mark-to-market and final closed-trade accounting use the same TP1 per-leg classification.
- The actual TP1 liquidity flag survives state persistence and is retained in TradeRecord.
- Gap fills remain priced at the target level rather than granting opening-price improvement. This is deliberately conservative on price; the fix changes liquidity/fee classification only.

Regression coverage: long TP1 gap-through vs ordinary intrabar TP1 touch; long and short TP2 gap-through; independent fee/slippage math for the TP1 and final legs; state restore of an actual taker TP1 classification. Research CI [#41720537099](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41720537099) completed SUCCESS: **52/52 steps**.

**Residual execution limit:** a non-gap OHLC touch is still only a maker proxy. The replay has no L2 order book, queue position, partial fills, cancel/replace latency or adverse-selection model. This correction prevents a known gap-through maker over-credit; it does not prove real maker execution.

This supersedes the earlier simplified note in the fee section that any configured take-profit exit is maker whenever maker_exits is true.


**Scope clarification for the current H1 portfolio runner:** scripts/run_h1_shared_capital_portfolio_validation.py explicitly sets maker_entry_and_tp1=True and maker_tp1_and_target=False (both in the engine setup and frozen-config manifest). Thus H1 uses maker entry with taker TP1/TP2 exits; the gap-aware maker-target correction does not alter that H1 execution configuration or its baseline. It protects other engine configurations and any future maker-target ablation from undercharging marketable TP gaps.
