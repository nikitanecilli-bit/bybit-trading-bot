# Initial Stop ATR Sensitivity — Bybit BTC/ETH H1
Date: 2026-11-25
Branch: research/h1-volume-lookback-provenance-fix
Workflow: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45661144975
Artifact: preliminary-bybit-initial-stop-sensitivity (54 configurations)

## Scope
Official Bybit public H1 archives only. Fixed Arm C: Donchian 48, EMA50 > EMA200, EMA200 rising over 5 bars, close > EMA200, volume ratio 1.6. Tested initial stops 2.5 / 3.0 / 3.5 ATR(14), folds 50–65%, 65–80%, 80–100%, cost multipliers 1.0 / 1.5 / 2.0. Position quantity is recalculated from each fold's current equity to target 1% nominal initial risk. TP1=2R on 50%, TP2=5R on remainder, 3 ATR trailing after TP1, time exit 32 bars. One position at a time.

## Aggregate results
Net PnL below is the arithmetic sum of the three independent fold PnLs (each fold starts with 10,000 USDT); it is not a compounded portfolio return. Compounded returns below are calculated by chaining the three reported fold returns, as a comparison aid only; folds remain separate historical slices.

### BTCUSDT
| Stop | Trades | Net 1x | Net 1.5x | Net 2x | Positive folds 1x | Worst fold 1x |
|---|---:|---:|---:|---:|---:|---:|
| 2.5 ATR | 151 | +1,385.98 | +510.01 | -337.59 | 2/3 | -0.45% |
| 3.0 ATR | 149 | +1,686.02 | +954.20 | +241.87 | 2/3 | -0.51% |
| 3.5 ATR | 143 | +1,781.51 | +1,169.16 | +570.50 | 3/3 | +0.46% |

Compounded fold return:
| Stop | 1x | 1.5x | 2x |
|---|---:|---:|---:|
| 2.5 ATR | +14.22% | +4.74% | -3.94% |
| 3.0 ATR | +17.48% | +9.38% | +1.82% |
| 3.5 ATR | +18.60% | +11.77% | +5.32% |

At 2x costs, BTC fold returns:
- 2.5 ATR: +6.20%, -0.28%, -9.29%.
- 3.0 ATR: +7.24%, +3.00%, -7.82%.
- 3.5 ATR: +3.83%, +7.63%, -5.76%.

### ETHUSDT
| Stop | Trades | Net 1x | Net 1.5x | Net 2x | Positive folds 1x | Worst fold 1x |
|---|---:|---:|---:|---:|---:|---:|
| 2.5 ATR | 112 | +756.47 | +303.71 | -142.54 | 2/3 | -3.75% |
| 3.0 ATR | 108 | +723.10 | +358.37 | -2.10 | 2/3 | -1.99% |
| 3.5 ATR | 108 | +483.70 | +173.65 | -133.31 | 2/3 | -1.12% |

Compounded fold return:
| Stop | 1x | 1.5x | 2x |
|---|---:|---:|---:|
| 2.5 ATR | +7.45% | +2.80% | -1.65% |
| 3.0 ATR | +7.19% | +3.43% | -0.19% |
| 3.5 ATR | +4.81% | +1.64% | -1.42% |

ETH does not validate a wider stop as a general asset-independent improvement. At 1.5x and 2x costs, the 3.0 ATR aggregate is marginally best, but it is not consistently profitable across folds.

## Exit diagnosis (1x costs)
BTC:
| Stop | Initial stop count | Initial-stop net PnL | Time exits | Time-exit net PnL | Trailing stops | Trailing net PnL |
|---|---:|---:|---:|---:|---:|---:|
| 2.5 ATR | 74 | -8,680.21 | 55 | +5,509.53 | 13 | +1,832.92 |
| 3.0 ATR | 63 | -7,326.98 | 68 | +4,914.04 | 9 | +1,318.20 |
| 3.5 ATR | 52 | -5,905.94 | 79 | +5,039.04 | 6 | +926.96 |

All initial-stop exits in this BTC sample were losing trades. Wider stops reduce the number of initial-stop exits and shift more trades into time exits, but trailing/TP2 contribution also declines. This is not proof that simply widening the stop creates a durable edge.

## Exploratory uncertainty check
A circular moving-block bootstrap was applied to BTC trade PnLs separately within each fold and stop setting: 20,000 resamples, blocks of 5 consecutive trades, wraparound, fixed seed 20261125. This preserves some local sequencing but is a rough diagnostic; it does not model market-path uncertainty or validate the strategy.

At 1x costs, the 95% bootstrap interval for total fold PnL crossed zero in every fold/stop combination except Fold 2 with 3.5 ATR (approximately +112 to +2,046 USDT). At 2x costs, every fold/stop interval crossed zero. This reinforces that the apparent aggregate advantage is uncertain.

## Entry-quality diagnostic (preliminary local calculation; reproducible workflow added)
Features are measured at the signal candle close, before entry at the next candle open. For the 3.5 ATR BTC candidate, 1x costs:

| Fold | Trades | Win rate | Median ATR% | Median volume ratio | Median EMA spread% | Median 6h momentum% | Median 24h momentum% | Median forward 6h return% | Median forward 32h return% |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 32 | 43.8% | 0.609 | 5.324 | 0.952 | 1.664 | 2.668 | +0.232 | -0.353 |
| 2 | 41 | 58.5% | 0.680 | 3.765 | 1.647 | 1.981 | 2.688 | +0.031 | +0.827 |
| 3 | 70 | 41.4% | 0.551 | 3.054 | 1.038 | 1.179 | 1.990 | -0.135 | -0.073 |

Fold 3's signals had weaker preceding momentum and lower volume expansion than Fold 1/2. Median forward 6h/32h returns were also weaker. This is a description of the market period, not evidence that these features can identify future winners.

Within Fold 3, 3.5 ATR winning and losing trades had very similar pre-entry medians: 6h momentum 1.033% vs 1.089%, volume ratio 2.666 vs 3.075, ATR% 0.526 vs 0.583. There is no clean one-variable separation that justifies a filter. Do not add thresholds based on this sample.

## Interpretation
1. 3.5 ATR is the strongest of the tested BTC settings on aggregate, including under 1.5x and 2x cost stress.
2. It is not robust enough for selection: BTC Fold 3 remains negative at 1.5x and 2x costs for all tested stops; at 2x even 3.5 ATR Fold 3 is -5.76%.
3. ETH does not reproduce the BTC result. Do not generalize 3.5 ATR to ETH.
4. No pre-entry filter is supported by this diagnostic.
5. Do not promote any stop setting to live trading. These are OHLCV-only results without funding, mark-price liquidation, historical instrument specs/risk tiers, spread, and execution/fill modeling.
6. Fold PnLs are independent 10,000 USDT-start simulations. Summed PnL is useful for comparing configurations, but must not be described as a continuous compounded equity curve.

## Next research step
Do not widen the stop further or optimize entry thresholds on these same folds. Keep 3.0 and 3.5 ATR as BTC research candidates only. Next, validate the diagnostics workflow and freeze a candidate before testing on genuinely untouched future Bybit data when available. Any filter proposal must be preregistered and evaluated on a separate untouched period. Do not optimize ETH alongside BTC.
