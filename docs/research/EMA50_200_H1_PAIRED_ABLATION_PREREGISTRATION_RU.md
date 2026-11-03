# EMA50/EMA200 H1 paired ablation — preregistration

**Status:** protocol frozen for future Bybit-native validation; no market PnL replay has been run.  
**Research branch:** `research/market-regime-v1-main`  
**Purpose:** test whether a causal EMA50/EMA200 trend gate improves the existing long-only H1 Donchian breakout without changing its execution or risk model.

## 1. Hypothesis

A long H1 Donchian breakout is eligible only when the same completed H1 candle is labelled `up` by all three causal conditions:

1. EMA50 > EMA200;
2. EMA200 is rising versus its value five completed H1 candles earlier;
3. current completed close > EMA200.

A `down` or `neutral` label blocks a long signal. This is a filter on the existing signal, not a new entry/exit strategy. H-C post-break invalidation and H-A relative-strength conditions are not combined with this test.

## 2. EMA initialization and causality

- EMA periods: fast 50, slow 200; slow slope lookback: 5 H1 bars.
- Recursive EMA seed is the first close in the supplied chronological history.
- Fixed burn-in: 1,000 completed H1 candles (5× EMA200) before the first scored candle. Labels before the burn-in are forced to `neutral`.
- Precompute labels once per symbol from the full chronological history available through the current fold end.
- Lookup only by exact current completed-candle open timestamp. No nearest timestamp, prior-bar fallback or next-bar label is allowed.
- Missing timestamps, non-monotonic/duplicate timestamps, non-contiguous H1 candles or insufficient pre-roll fail closed.
- The current engine's 200-candle calculation window is not enlarged; full-history context is passed separately.

## 3. Data and universe gates

No PnL replay may start until all required inputs are present and pass their existing provenance/coverage checks:

- Official Bybit V5 linear USDT perpetual H1 trade OHLCV for the selected instruments.
- Bybit funding settlements and corresponding Mark OHLC candles.
- Dated Bybit instrument specifications and risk-limit tier snapshots covering the scored period.
- Bybit linear lifecycle/universe snapshot used by the train-only selector.
- Frozen top-five selection manifest with exact input/code hashes and common H1 timestamp overlap.

The top-five basket must be selected only by the existing train-only selector; no CryptoFetch PnL ranking or hindsight shortlist is allowed. Re-run the selector after final replay-critical code freeze because the selector manifest locks the H1 runner and EMA helper hashes.

CryptoFetch archives are development-only and already consumed for earlier strategy research. They are not a fresh holdout and must not be used for this EMA PnL comparison.

## 4. Paired variants

For each identical fold, selected five-symbol basket, volume threshold, breakout-ATR threshold and cost multiplier, run exactly two independent portfolios:

- **Baseline:** existing long-only H1 Donchian(20)+volume strategy, EMA gate disabled.
- **Candidate:** same strategy and settings, with the EMA50/200-up gate enabled.

Both variants use the same 10,000 USDT starting capital, same shared-capital portfolio engine, same risk/execution configuration and same input candles. The two variants do not share capital with each other.

The manual workflow exposes `ema50_200_comparison=off|paired`. `off` is the default baseline-only mode. `paired` runs both variants and writes explicit paired deltas to the validation manifest. Duplicate or missing pair legs are fatal.

## 5. Frozen execution and portfolio configuration

| Parameter | Frozen value |
|---|---:|
| Timeframe | H1 |
| Direction | Long-only |
| Donchian period | 20 |
| ATR period | 14 |
| Stop distance | 2.5 ATR |
| TP1 | 2R |
| TP2 | 5R |
| ATR trailing stop | 3.0 ATR |
| Maximum hold | 32 H1 bars |
| Entry | Maker limit proxy; 20 bps offset, 5 bps penetration |
| Limit wait | 3 H1 bars |
| TP1 / target liquidity | Maker TP1; market/taker final target |
| Starting capital per variant | 10,000 USDT |
| Risk per trade | 1.0% |
| Portfolio risk cap | 2.0% |
| Maximum concurrent positions | 5 |
| Leverage | 5x isolated model (explicitly set in runner as ISOLATED_5X / 5.0) |
| Daily stop | 5% |
| Emergency kill switch | 30% |
| Maximum chase | 1.5% |
| Cost multipliers | 1.0x / 1.5x / 2.0x |

No setting may be altered after the confirm fold begins. Existing execution-model limitations remain: OHLC limit penetration is not queue proof; spread, L2 priority, partial-fill adverse selection and account-specific fee tier are not fully represented. Funding is modelled from archived settlements using the runner's timestamp-aligned Mark-candle settlement-price proxy. Liquidation remains a position-level isolated approximation, not full account-level UTA/Classic semantics.

## 6. Fold protocol and selection

- **Explore:** folds 1 and 2 only. The volume and breakout-ATR thresholds may be selected from the predeclared grid using these folds. They are development/selection data, not OOS proof.
- **Confirm:** fold 3 only, using one frozen volume threshold and one frozen breakout-ATR threshold chosen before the confirm run. Baseline and EMA candidate are paired on the same fold.
- The three cost multipliers are stress cases, not three opportunities to choose the most flattering result. The primary cost case is 2.0x; 1.0x and 1.5x are sensitivity checks.
- The paired manifest must contain exactly one baseline and one EMA candidate for every fold/config/cost key. Pair mismatch fails closed. It also verifies exact equality of timeframe, selected symbol list/count, common H1 bar count, fold start/end, starting capital and maximum concurrent positions before calculating deltas.
- Fold 3 is a one-shot confirmation. If its result is used to change EMA parameters, thresholds, execution assumptions or risk settings, fold 3 is spent and cannot be called an untouched holdout afterward. Any changed candidate then requires a later independent holdout.

## 7. Metrics and decision rule

Primary comparison: `EMA candidate net PnL − baseline net PnL` at 2.0x cost on confirm fold 3.

The candidate is eligible for further validation only if all are true on the 2.0x confirm case:

1. EMA candidate net PnL is positive;
2. paired net-PnL delta is positive;
3. profit factor > 1.0;
4. expectancy > 0;
5. maximum drawdown does not exceed the baseline by more than 2 percentage points;
6. geometric monthly-equivalent net return is at least +20%.

The 1.0x and 1.5x cases must be reported alongside the primary result; they cannot replace a failed 2.0x primary case. Report monthly equity and losing-month frequency separately—geometric monthly-equivalent return is not proof that every calendar month was profitable.

Passing this single confirm fold only permits a later independent holdout and paper-forward validation. It does **not** prove stable +20% net/month, does not authorize live orders and does not authorize private Bybit API/account connection. The user's API hold remains in force until the strategy has demonstrated the required paper profitability.

## 8. Current status

- EMA context, paired runner mode, exact pairing and fail-closed comparison manifest are implemented.
- Research CI [#41728994842](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41728994842) passed 55/55 paired-comparison steps; follow-up integrity hardening [#41730087544](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41730087544) passed 54/54.
- Bybit-native H1/funding/mark/spec/risk archives are not currently available in the repository.
- No EMA PnL replay, no Bybit API connection, no external data download and no orders have been performed.
