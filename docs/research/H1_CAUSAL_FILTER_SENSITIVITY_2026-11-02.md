# H1 predeclared causal filter sensitivity — 2026-11-02

## Provenance and design

- Workflow: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41425546290
- Script: scripts/test_h1_predeclared_causal_filters.py
- Commit: 6536ae3bca1e3407bc0a5031e64ebf23c615b93e
- Same 25-symbol continuous-coverage H1 universe and two fixed windows as H1_TWO_PERIOD_SCREEN_2026-11-02.md.
- Same engine baseline settings, independent 10,000-USDT per-symbol simulations, 1% risk/trade.
- Filters are applied at signal time inside the engine, so skipped signals do not become trades. No post-hoc filtering of closed trades.
- Trend and ATR features use only completed candles strictly before the signal candle. The 24h trend rule aligns long signals with positive prior-24h return and short signals with negative prior-24h return.
- The ATR rule is fixed at prior ATR(14)/close >= 1.1%; it is not recalibrated between periods.
- The comparison set was frozen as six diagnostic variants, not searched over parameter grids.

## Aggregate comparison

| Period | Filter | Trades | Profitable symbols | Sum net PnL, USDT | Median symbol PF |
|---|---|---:|---:|---:|---:|
| Screening | Baseline | 1,752 | 9/25 | -1,886.09 | 0.95 |
| Screening | Exclude US session | 1,283 | 15/25 | +9,959.67 | 1.08 |
| Screening | Align with prior 24h trend | 1,595 | 11/25 | +364.96 | 0.96 |
| Screening | ATR >= 1.1% | 754 | 9/25 | -4,624.47 | 0.79 |
| Screening | 24h alignment + ATR >= 1.1% | 714 | 10/25 | -4,174.60 | 0.77 |
| Screening | 24h alignment + exclude US | 1,156 | 17/25 | +11,558.02 | 1.13 |
| Forward | Baseline | 1,777 | 6/25 | -14,789.82 | 0.82 |
| Forward | Exclude US session | 1,425 | 11/25 | -5,020.33 | 0.96 |
| Forward | Align with prior 24h trend | 1,623 | 7/25 | -12,047.23 | 0.87 |
| Forward | ATR >= 1.1% | 623 | 11/25 | +879.19 | 0.90 |
| Forward | 24h alignment + ATR >= 1.1% | 587 | 9/25 | -461.93 | 0.89 |
| Forward | 24h alignment + exclude US | 1,265 | 14/25 | -459.86 | 1.03 |

The net PnL column is the sum of independent per-symbol runs and is not a shared-capital portfolio result. Median PF is the median of per-symbol profit factors; it is not portfolio PF.

## Findings

1. **US-session exclusion is the clearest repeatable improvement, but not a complete solution.** It moves the screening aggregate from -1.89k to +9.96k and the forward aggregate from -14.79k to -5.02k. It improves both periods materially, but the forward result remains negative.
2. **24h trend alignment alone is weak.** It nearly reaches flat in the screening period but remains deeply negative forward. A simplistic short-horizon trend filter is not enough.
3. **A fixed ATR >= 1.1% threshold is regime-sensitive.** It is strongly negative in the screening window and mildly positive in the forward window. It cannot be accepted as a universal filter.
4. **24h alignment + US-session exclusion is the strongest of these six variants.** It produces +11.56k screening and -0.46k forward, with 14/25 forward symbols positive and median forward symbol PF 1.03. This is a major improvement over baseline, but the forward aggregate is still slightly negative and the median PF is only marginally above 1.
5. **The best candidate is not validated.** These filters were motivated by diagnostics on the same two periods. The later window is therefore not an untouched holdout for this filter family. The near-flat forward result may be selection bias, and funding/mark-price data is absent.

## Trade mechanics behind the regime change

The trade attribution run found:
- Stop-loss exits were almost unchanged: 910 screening vs 926 forward.
- Take-profit exits fell from 66 to 46.
- Time-stop exits increased from 478 to 558.
- Trailing-stop exits fell from 279 to 240.
- US-session net PnL was negative in both windows: -9.84k and -10.68k USDT.
- In the forward period, short trades lost more than long trades (-11.68k vs -3.11k USDT).
- In the screening period, low-ATR tercile trades were positive (+5.08k), while in the forward period low and middle terciles were negative (-9.85k and -6.05k) and high ATR was only mildly positive (+1.11k). Terciles are period-relative diagnostics, not deployable fixed thresholds.

These patterns are consistent with weaker follow-through and a changed volatility/session relationship, but OHLCV alone cannot establish the precise intrabar cause of each stop or missed target.

## Decision and next experiment

- Do not deploy any filter from this report.
- Keep the baseline unchanged and preserve all six variants as research comparisons.
- Do not select a top-5 instrument basket from these same results.
- The next valid test should freeze one candidate rule (24h directional alignment + no US session) and evaluate it on a genuinely later, untouched data window after extending the historical archive. If no new history can be obtained, use nested walk-forward folds and clearly label them as repeated model selection rather than final validation.
- Before exchange-realistic evaluation, obtain permitted historical Bybit funding/mark-price and instrument-spec data. Current archive inventory is OHLCV-only Binance proxy data.

No production code, live configuration, or main branch was changed.
