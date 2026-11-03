# H-C — post-break continuation / early invalidation

**Status:** implemented behind a disabled-by-default research flag; NOT PnL-tested, NOT enabled for live, NOT approved for deployment.
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

## 5. Implementation and synthetic regression coverage

Completed in the research branch:
- [x] Store the exact signal-time Donchian boundary in pending signal and open-position state; never recompute it using future candles.
- [x] Add an explicit, disabled-by-default configuration switch and an H1-only validation gate.
- [x] Preserve exact remaining quantity and TP1 realized leg through the early close; existing fee, slippage and funding accounting is reused by the normal close lifecycle.
- [x] Add deterministic tests for long/short symmetry, first/third-bar trigger, no wick-only trigger, no trigger after bar 3, stop/TP2 precedence, TP1 partial then retest close, strategy scope and no same-bar re-entry.
- [x] Add fail-closed tests for missing breakout boundary on pending fill/state restore, plus backward-compatible loading when the flag is disabled.
- [ ] Confirm exact baseline PnL parity with the H-C switch disabled. This requires a later replay and has deliberately NOT been run on the reused research folds.

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

## 8. Current implementation status

Completed in the research branch as provenance and disabled feature implementation:
- Baseline and H-A signal evaluators now emit the signal-time Donchian breakout boundary.
- The boundary is carried through pending orders, OpenPositionState, TradeRecord and the H-A trade/diagnostic ledger.
- State restoration validates a finite positive boundary while remaining backward-compatible with older backups that do not contain the optional field when H-C is disabled. With H-C enabled, an active baseline breakout position or pending signal inside the three-bar window without that boundary is rejected fail-closed.
- Tests cover long/short signal boundaries, state round-trip, invalid values and legacy backup loading.

The H-C close-based exit event is now implemented behind config key execution_and_exits.enable_post_break_invalidation, default false. It is H1-only and uses the fixed three-bar horizon. Its preregistered scope is the frozen H1 baseline strategy H1-momentum-breakout only. H-A-relative-strength-breakout is a rejected candidate and is explicitly excluded; the implementation and tests preserve that exclusion.

The event runs after intrabar stop/liquidation/TP handling and kill-switch priority. It closes at the completed candle close only when the position remains open and the close has returned inside the stored boundary. TP1 partial state is preserved and only the remaining quantity is closed. Missing signal-time boundary fails closed on baseline pending fill, state restore or active position management.

Synthetic CI coverage: Research CI [41676357873](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41676357873) SUCCESS. H-C semantics **9/9 tests passed**; full state-persistence suite **67/67 passed**; complete Research engine checks passed. Covered disabled-by-default baseline behavior, fail-closed pending entry, long/short symmetry, first/second/third-bar window, wick-only rejection, no trigger after bar 3, stop/TP2 precedence, TP1 partial then retest, H1-only config, H-A exclusion and no same-bar re-entry.

This is implementation correctness only. The flag remains false by default; no market PnL run has been launched and the feature must not be enabled live.


### 8.1. TP liquidity and cost-accounting hardening (2026-11-04)

The engine now records TP1 and final TP2 liquidity per execution leg. A target limit gapped through at candle open is classified taker; a non-gap intrabar touch remains a maker proxy. H-C close-based invalidation is always taker. Mark-to-market consumes the actual TP1 classification while the remaining open leg is conservatively marked with taker exit cost. The H-A trade ledger exports these fields for future audit.

Synthetic coverage: Research CI [#41720355038](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41720355038) SUCCESS, 52/52; H-C semantics 10/10. No PnL replay. Maker queue, spread and adverse selection remain unmodeled; do not treat OHLC touch as confirmed maker fill. Follow-up state round-trip for explicit tp1_maker=False passed in [#41720499938](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41720499938), 52/52 steps.

## 9. Current blockers

- Bybit-native historical market and point-in-time universe archives are not yet complete/verified in the repository.
- The current H-A artifacts predate the latest trade-journal extension and therefore still lack TP1 partial-state fields. The research branch now retains initial stop geometry, TP1 hit/time/realized gross, remaining fraction, final stop and breakout level in TradeRecord, and the H-A runner exports them on future runs. H-C itself now executes inside the engine lifecycle so event priority and partial quantities are exact; do not infer counterfactual PnL from old final trade rows.
- Existing H-A folds are development data only.

**No market PnL run has been launched for H-C.**
