# H1 Directional Scope Audit — 2026-11-03

## Status

**P1 — research-scope mismatch; no strategy code changed.**

The current Bybit-native H1 shared-capital runner and the Top-5 train-only selector are long-only, although the research plan explicitly says that a permanent long-only/short-only restriction is not justified until directional behavior is validated on the relevant folds.

## Confirmed implementation evidence

1. In `scripts/run_h1_shared_capital_portfolio_validation.py`, the wrapped signal evaluator returns `None` whenever `sig["direction"] != "long"`. Short signals never enter the shared-capital portfolio replay.
2. `scripts/select_h1_top5_train_only.py` imports and calls `run_portfolio_variant` from that runner. Therefore the train-only Top-5 ranking is also based on long-only PnL, not two-sided instrument quality.
3. The H1 shared-capital workflow accepts the resulting five-symbol selection manifest and enforces exactly five primary symbols. It does not independently restore short-side evidence.
4. The current research plan states that both long and short should remain available where signal symmetry is confirmed, and that a permanent directional restriction is not justified by the existing folds.

## Historical evidence — not sufficient to settle the question

The experiment ledger records E01, a 50-symbol / three-fold independent-symbol direction and execution ablation on proxy OHLCV:

- Long+short market: -16,911.93 USDT / 2,699 trades.
- Long-only market: +1,056.65 USDT / 1,458 trades.
- Long+short limit 20 bps: -261.36 USDT / 2,395 trades.
- Long-only limit 20 bps: +9,823.41 USDT / 1,308 trades.

These are **not shared-capital portfolio results**, and the limit-fill model is an OHLC proxy without queue priority, spread, partial fills or actual Bybit execution. The market long-only result also changes sign by fold (+2,815.06 / -732.75 / -1,025.66 USDT). The limit long-only result is positive in those historical folds, but it is still proxy evidence and cannot validate a Bybit-native two-sided or long-only portfolio.

## Why this matters

- Current Top-5 symbols are selected for long-only breakout performance. They are not proven to be the best two-sided instruments.
- A combined long/short portfolio can have different trade frequency, capital overlap, funding exposure, risk-tier sizing and drawdown than a long-only portfolio.
- The current H1 runner's results must be labelled **long-only H1 shared-capital results**, not generic H1 strategy performance.
- The Top-5 selector's output should not be reused for a two-sided strategy without a direction-aware re-selection.

## Required next experiment — after Funding completeness is proven

Keep the current long-only runner unchanged as a reproducible research variant. Add a separately versioned directional ablation on the same Bybit-native H1 history, common timestamps, costs and shared-capital rules:

1. Long-only.
2. Short-only.
3. Long+short.
4. If evidence supports it, a predeclared regime-conditioned direction policy.

Run direction-aware train-only symbol selection for each mode or use one predeclared common universe to isolate direction. Compare fill rate, trades, fees, slippage, Funding, net PnL, expectancy, profit factor, portfolio drawdown, concurrent exposure and symbol contribution. Select on training folds only; reserve the final chronological fold for one-shot confirmation.

Do not run this experiment until the Funding archive completeness gate, Mark coverage, dated instrument specs and risk-tier gates are satisfied. Do not alter the current strategy or claim a directional edge based on E01 proxy results.

## Actions in this audit

- No strategy parameters changed.
- No Bybit API or live orders used.
- No new market PnL replay run.
- The issue is documented as a research-scope blocker for interpreting the current H1 Top-5 workflow.


## Provenance clarification

The long-only scope is explicitly recorded in both artifacts: the selector writes strategy_config.direction = long_only, and the portfolio runner writes strategy_and_execution.direction = long_only. This is not a missing-manifest-field defect. The blocker is that the selected strategy scope is narrower than a generic/two-sided H1 claim and conflicts with the research plan's instruction not to make permanent directional restrictions from proxy evidence.
