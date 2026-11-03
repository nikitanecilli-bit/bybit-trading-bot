# H-C — post-break continuation / early invalidation

**Status:** design only; NOT IMPLEMENTED, NOT RUN, NOT APPROVED FOR LIVE.
**Created:** 2026-11-03
**Parent evidence:** H-A diagnostic artifacts and H_A_RELATIVE_STRENGTH_BREAKOUT_PREREGISTRATION_RU.md, sections 11–12.

## 1. Hypothesis

A breakout that closes back inside its pre-break Donchian boundary within the first three completed H1 bars after entry has a higher probability of becoming a stop-loss trade than a breakout that holds outside the boundary. A close-based early invalidation may reduce the loss tail while retaining a larger share of true continuation trades.

This is a post-entry management hypothesis, not a pre-entry signal filter.

## 2. Evidence motivating the hypothesis

On the already-used CryptoFetch/Binance-style H-A diagnostic sample:
- H-A stop-loss cohort: 61.6% of eligible trades closed back inside the prior Donchian boundary within the first three completed H1 bars; profitable exit cohort: 41.6%.
- Mean directional close return after three completed bars: -0.104R for stop-loss trades vs +0.222R for profitable exits; rank AUC for lower return identifying stop-loss outcomes ≈0.70.
- The retest association had the same direction in all three historical folds and also appeared in the frozen baseline.
- Pre-entry signal-candle features were weak (AUC mostly 0.48–0.55).

These folds have already been inspected. The evidence is exploratory, not independent validation. The 3-bar window was selected after observing these data and therefore requires a separate untouched period.

## 3. Frozen baseline to compare

Use the same H1 baseline configuration as the H-A replay, with the invalidation rule disabled:
- Donchian period: 20 completed bars.
- ATR period: 14.
- Minimum volume ratio: 1.6.
- Stop distance: 2.5 ATR.
- TP1: 2.0R; TP2: 5.0R.
- ATR trailing multiplier: 3.0.
- Maximum holding period: 32 H1 bars.
- Maximum chase: 1.5%.
- Market entries and market exits; maker flags disabled.
- Starting equity: 10,000 USDT.
- Risk per trade: 0.5%; portfolio risk cap: 2%.
- Maximum concurrent positions: 5.
- Leverage parameter: 5; daily stop: 5%; emergency kill-switch: 30%.
- Shared-capital portfolio simulation. Identical universe, timestamps, sizing, costs and risk controls in baseline and H-C.

Any exchange-realism inputs (historical instrument specs, risk tiers, funding settlements, mark prices, fees and quantity steps) must be dated and complete for every symbol and fold. Do not backdate current snapshots.

## 4. One frozen H-C rule

At signal time, store the exact prior 20-bar Donchian breakout boundary:
- Long: breakout_level = max(high) of the 20 completed bars before the signal candle.
- Short: breakout_level = min(low) of the 20 completed bars before the signal candle.

After a market entry, evaluate only the first three completed H1 bars, including the entry bar:
- Long invalidation: a completed H1 candle closes at or below breakout_level.
- Short invalidation: a completed H1 candle closes at or above breakout_level.
- A wick through the boundary without a close back inside does not trigger.
- On the first qualifying close, close the remaining position at that candle's close using the frozen market-exit fee and adverse-slippage model.
- No re-entry or retry is allowed for the same signal.
- If the position has already been closed by stop, liquidation, TP2 or trailing exit before the close check, no retest exit is generated.
- If TP1 was executed intrabar and the position remains open, preserve its realized PnL and quantity reduction, then close only the remaining quantity at the retest close.
- Existing stop/liquidation/TP event priority remains unchanged. The close-based retest check runs only after intrabar event handling and only if the position is still open.
- After the third completed H1 bar, normal baseline management resumes unchanged.

No other filters or parameters may change.

## 5. Required implementation and test coverage before any replay

1. Store the exact signal-time Donchian boundary in pending signal and open-position state; never recompute it using future candles.
2. Add an explicit, disabled-by-default configuration switch and an H1-only validation gate.
3. Preserve exact position quantity, TP1 realized leg, remaining fraction, fees, slippage, funding, risk and execution provenance through the early close.
4. Add deterministic tests for long/short symmetry, first-bar/second-bar/third-bar trigger, no wick-only trigger, no trigger after bar 3, stop/TP precedence, TP1 partial then retest close, and no re-entry.
5. Add a path-causality test proving the rule cannot see the close of a candle before it is complete.
6. Confirm baseline metrics reproduce exactly with the H-C switch disabled.

## 6. Data and validation gate

Do not run this on the already-used 2026-04-27 through 2026-10-26 folds and do not perform a threshold sweep.

Required before a market replay:
- An untouched time period or new forward data not used to discover this rule.
- Prefer Bybit-native H1 OHLCV with historical point-in-time linear-universe membership.
- Dated instrument specifications and risk tiers available as of each entry.
- Complete funding settlements and mark-price coverage for every scored symbol.
- Exchange-consistent fee tier, quantity rounding, margin and liquidation assumptions.
- One preregistered shared-capital run comparing baseline vs H-C; no repeated tuning.

The earlier 2025-10 to 2026-04 CryptoFetch history may be considered only as a separately labelled reverse-time robustness check after the prior experiment ledger has been reconciled. It is not Bybit-native, its universe is survivor-selected, and it cannot be called forward OOS.

## 7. Decision criteria and reporting

Primary outcome: shared-account net PnL after fees, slippage and funding, compared with the frozen baseline.

Always report, by fold and symbol:
- net PnL, gross PnL, fees, slippage, funding;
- expectancy in R, profit factor, max drawdown and return;
- stop-loss count and average loss;
- retest-exit count, average retest-exit R and time-in-trade;
- TP1 partial count and remaining quantity closed;
- trade count, turnover, concurrent positions and kill-switch events.

Promote only if the frozen H-C result is net profitable after all modeled costs, improves net PnL versus baseline on the untouched validation period, and does not obtain its result from one symbol or one fold. If it fails, reject; do not tune the 3-bar window or boundary definition on the same holdout.

## 8. Current blockers

- Bybit-native historical market and point-in-time universe archives are not yet complete/verified in the repository.
- The current H-A artifacts predate the latest trade-journal extension and therefore still lack TP1 partial-state fields. The research branch now retains initial stop geometry, TP1 hit/time/realized gross, remaining fraction and final stop in TradeRecord, and the H-A runner exports them on future runs. H-C must still be implemented inside the engine lifecycle so event priority and partial quantities are exact; do not infer counterfactual PnL from old final trade rows.
- Existing H-A folds are development data only.

**No market PnL run has been launched for H-C.**
