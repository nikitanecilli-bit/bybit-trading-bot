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
To avoid treating a small number of profitable trades as conclusive, a moving-block bootstrap was applied to BTC trade PnLs separately within each fold and stop setting: 20,000 resamples, blocks of 5 consecutive trades, with wraparound. This preserves some local sequencing but is still only a rough diagnostic; it does not model market-path uncertainty or validate the strategy.

At 1x costs, the 95% bootstrap interval for total fold PnL crossed zero in every fold/stop combination except Fold 2 with 3.5 ATR (approximately +112 to +2,046 USDT). At 2x costs, every fold/stop interval crossed zero. This reinforces that the apparent aggregate advantage is uncertain and that the strategy has not established a robust positive expectancy.

## Interpretation
1. 3.5 ATR is the strongest of the tested BTC settings on the aggregate, including under 1.5x and 2x cost stress.
2. The result is not robust enough for selection: BTC fold 3 remains negative at 1.5x and 2x costs for all tested stops; at 2x even the best 3.5 ATR fold 3 is -5.76%.
3. ETH does not reproduce the BTC result. Do not generalize 3.5 ATR to ETH.
4. Do not promote any stop setting to live trading. These are OHLCV-only results without funding, mark-price liquidation, historical instrument specs/risk tiers, spread, and execution/fill modeling.
5. Fold PnLs are independent 10,000 USDT-start simulations. Summed PnL is useful for comparing configurations, but must not be described as a continuous compounded equity curve.

## Next research step
Keep 3.0 and 3.5 ATR as BTC research candidates, not selected production parameters. Before further parameter search, inspect whether the persistent weak third fold reflects entry-signal quality or adverse market regime, using only pre-entry information and without adding a filter based on the same test-fold outcomes. Then validate the frozen candidate on a genuinely untouched later Bybit data period if/when an official archive covering it is available. Do not optimize ETH alongside BTC.
