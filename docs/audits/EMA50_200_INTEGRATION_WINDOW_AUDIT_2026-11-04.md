# EMA50/EMA200 integration window audit — 2026-11-04

Branch: `research/market-regime-v1-main`  
Status: **CONFIRMED INTEGRATION BLOCKER — DO NOT WIRE THE FILTER DIRECTLY INTO evaluate_signal**  
Scope: `market_structure.py`, `Bybit_Trading_Engine_v14_research.py`, `scripts/run_h1_shared_capital_portfolio_validation.py`, `tests/test_market_structure.py`  
Market PnL replay: **NOT RUN**

## Finding

The research-only EMA helper supports a 50/200 trend definition with a 5-bar slow-EMA slope check. In `trend_direction_series()`, the first directional label can only be emitted at index `slow + slope`; with fast=50, slow=200 and slope=5, the first possible label is index 205 (the 206th candle).

The engine defines:

```python
CALC_WINDOW = 200
```

Both normal synchronized `run_simulation_pass()` and the H1 runner ultimately call `QuantStrategyCore.evaluate_signal()` with only the last `CALC_WINDOW` candles. `evaluate_signal()` receives the current completed signal candle plus the truncated history. Therefore, a naive call to `trend_direction(bars, fast=50, slow=200, slope=5)` from inside `evaluate_signal()` will always return `neutral`: it never receives the 206 observations needed to warm up the helper.

This is a confirmed architectural mismatch, not a current live bug. `market_structure.py` is currently research-only and the production/research engine does not import or apply its EMA filter to signals. The runner includes the module in its code-provenance list only.

## Correct integration shape

Do not blindly increase `CALC_WINDOW` or recalculate a full EMA for every signal.

For a future preregistered variant:

1. Before replay, compute `trend_direction_series()` once for each symbol from the complete chronological candle series available up to the fold end. The helper is O(N) and each label is causal; later candles do not rewrite earlier labels.
2. Preserve the full-series index/timestamp mapping: `(symbol, candle.ts) -> trend label`.
3. At signal evaluation, look up the label for the current completed candle timestamp. Do not use the next candle's label or a stale prior-bar label.
4. For a directional gate, allow long only when the same-bar label is `up`, short only when it is `down`; neutral blocks the signal. The initial H1 candidate is long-only, so it must not silently imply a symmetric short strategy.
5. Keep the existing execution, stop, TP, costs, portfolio capital and risk limits identical between baseline and gated ablation.
6. Include the full input candle hashes, EMA parameters, helper code hash and timestamp-to-label provenance in the experiment manifest.
7. Add tests for: 200-bar truncated history returns neutral; precomputed full-history labels are prefix-invariant; wrapper looks up the exact current bar; no future timestamps are present in the context; missing label fails closed; long/short direction handling is explicit.

## Replay callback observation

The H1 runner monkeypatches `QuantStrategyCore.evaluate_signal` to apply its existing long-only, volume and breakout-distance conditions. This wrapper is a natural place to add a precomputed same-bar label lookup for a separate research variant. The normal synchronized replay currently does not accept the sparse-replay custom `signal_evaluator` callback, so the implementation should either extend the regular replay API with a narrowly scoped deterministic signal-context callback or keep the variant wrapper local to the H1 runner. Do not alter the baseline path.

## Indicator semantics

The 50/200 direction helper requires all of:
- fast EMA above/below slow EMA;
- slow EMA slope over the configured lookback with the same sign;
- current close above/below slow EMA.

Thus a countertrend rally while price remains below a falling EMA200 remains labelled bearish until the slow trend confirms a reversal. The synthetic tests were corrected to reflect the actual EMA state at their final bar; indicator logic was not loosened.

Research CI [#41726204938](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41726204938) passed **53/53 steps** at code commit `2f7c590e70da47ab855db31d9f823d8134ac7cd5`. This is deterministic indicator/engine regression evidence only; the filter has no PnL evidence and is not integrated.

## Decision

- Keep EMA50/EMA200 as an unproven research hypothesis.
- Do not run market PnL until the Funding/Mark completeness and Bybit-native archive gates are actually satisfied.
- Do not change the engine's `CALC_WINDOW` or default signal behavior for this audit.
- No live API, new archive collection, real orders, or strategy execution changes were made.


### Warm-up boundary regression — 2026-11-04

Added an explicit unit regression proving that the 50/200 helper remains neutral at 205 candles and emits the first directional label at 206 candles for the configured 5-bar slow-EMA slope. Research CI [#41726808976](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41726808976) completed **SUCCESS, 53/53 steps** at commit `8876ee399118837b35a3fcfdf58d2e117ec9fb72`. This locks the warm-up contract and makes the 200-bar engine-window mismatch executable rather than documentation-only.


## EMA initialization burn-in — additional caveat

The helper seeds each recursive EMA with the first close in the supplied series. The 206-candle minimum above is only the first mathematically computable directional label; it is **not** proof that EMA200 has converged away from its initial seed. With α=2/201, the seed's remaining weight after 200 updates is approximately 13.53%; after 1,000 updates (five EMA periods) it is approximately 0.00454%.

Therefore, a future full-history precomputation must preserve a substantial pre-roll before the first scored signal. A conservative design candidate is at least 5× the slow period (1,000 H1 bars for EMA200) before scoring, or an explicitly specified SMA-seeded EMA implementation with its own parity tests. The chosen initialization and burn-in must be frozen before any experiment; do not tune it on PnL. The 206-candle test documents the helper's current first-label boundary, not the recommended scoring pre-roll.


### Non-finite input hardening — 2026-11-04

The research-only EMA helper now rejects non-numeric/non-finite EMA inputs, and the trend helper rejects non-finite or non-positive close values instead of silently propagating NaN into neutral labels. Regression coverage includes NaN, +Infinity, -Infinity and zero close. Research CI [#41727040877](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41727040877) completed **SUCCESS, 53/53 steps** at code commit `18ea0707790e6830f0f9e40829d00cdf7c7a40fc`.
