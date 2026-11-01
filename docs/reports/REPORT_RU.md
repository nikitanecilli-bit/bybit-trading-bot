# Portfolio symbol ablation — sequential window test

- Engine: research copy `/mnt/data/v14_logic_research/Bybit_Trading_Engine_v14_Research.py`; production file unchanged.
- Data: 8 synchronized 15m OHLCV series, 2026-04-29 through 2026-10-26.
- Three consecutive validation folds cover 40–60%, 60–80%, and 80–100% of the candles. Each fold starts with 300 bars of warmup; entries before the fold start are blocked.
- Every fold starts with 10,000 USDT, same risk settings (1% risk, 5x leverage, 3 concurrent positions, daily stop 5%, kill switch 30%). Fold PnLs are diagnostic sums, not a continuous compounded account curve.
- Configurations: all symbols BASE; all symbols ADX(14) H1 >= 25; exclude BTC/ETH/SOL with ADX>=25; only SUI+BNB with ADX>=25. Same exit/fee/slippage logic in research engine.
- ADX uses only a fully closed hourly candle; no future candles used.
- Important limitation: data and strategy have been examined previously; this is sequential-window robustness analysis, not untouched final OOS.

## By fold
|   fold | window_start_utc          | window_end_utc            | config                    | symbols                                                           |   n_symbols |   trades |   net_pnl_usdt |   net_pf |   expectancy_r |   win_rate_pct |   max_dd_pct |   ending_equity_usdt |
|-------:|:--------------------------|:--------------------------|:--------------------------|:------------------------------------------------------------------|------------:|---------:|---------------:|---------:|---------------:|---------------:|-------------:|---------------------:|
|      1 | 2026-07-10T00:00:00+00:00 | 2026-08-14T23:45:00+00:00 | ALL_BASE                  | BNBUSDT;BTCUSDT;DOGEUSDT;ETHUSDT;PEPEUSDT;SOLUSDT;SUIUSDT;XRPUSDT |           8 |      104 |       -2947.85 |   0.3326 |        -0.4069 |        36.5385 |        30.17 |                  nan |
|      1 | 2026-07-10T00:00:00+00:00 | 2026-08-14T23:45:00+00:00 | ALL_ADX25                 | BNBUSDT;BTCUSDT;DOGEUSDT;ETHUSDT;PEPEUSDT;SOLUSDT;SUIUSDT;XRPUSDT |           8 |      111 |       -3019.61 |   0.3244 |        -0.3831 |        37.8378 |        30.2  |                  nan |
|      1 | 2026-07-10T00:00:00+00:00 | 2026-08-14T23:45:00+00:00 | EXCLUDE_BTC_ETH_SOL_ADX25 | BNBUSDT;DOGEUSDT;PEPEUSDT;SUIUSDT;XRPUSDT                         |           5 |       94 |       -3031.04 |   0.3052 |        -0.4315 |        31.9149 |        30.31 |                  nan |
|      1 | 2026-07-10T00:00:00+00:00 | 2026-08-14T23:45:00+00:00 | ONLY_SUI_BNB_ADX25        | SUIUSDT;BNBUSDT                                                   |           2 |       81 |       -2259.72 |   0.3274 |        -0.3619 |        38.2716 |        22.6  |                  nan |
|      2 | 2026-08-15T00:00:00+00:00 | 2026-09-19T23:45:00+00:00 | ALL_BASE                  | BNBUSDT;BTCUSDT;DOGEUSDT;ETHUSDT;PEPEUSDT;SOLUSDT;SUIUSDT;XRPUSDT |           8 |      243 |       -2963.79 |   0.6895 |        -0.2193 |        39.0947 |        30.95 |                  nan |
|      2 | 2026-08-15T00:00:00+00:00 | 2026-09-19T23:45:00+00:00 | ALL_ADX25                 | BNBUSDT;BTCUSDT;DOGEUSDT;ETHUSDT;PEPEUSDT;SOLUSDT;SUIUSDT;XRPUSDT |           8 |      192 |       -2222.39 |   0.7427 |        -0.1668 |        43.2292 |        30.18 |                  nan |
|      2 | 2026-08-15T00:00:00+00:00 | 2026-09-19T23:45:00+00:00 | EXCLUDE_BTC_ETH_SOL_ADX25 | BNBUSDT;DOGEUSDT;PEPEUSDT;SUIUSDT;XRPUSDT                         |           5 |      181 |       -2006.36 |   0.7587 |        -0.1361 |        44.7514 |        30.67 |                  nan |
|      2 | 2026-08-15T00:00:00+00:00 | 2026-09-19T23:45:00+00:00 | ONLY_SUI_BNB_ADX25        | SUIUSDT;BNBUSDT                                                   |           2 |      102 |       -2866.75 |   0.4266 |        -0.3566 |        34.3137 |        29.13 |                  nan |
|      3 | 2026-09-20T00:00:00+00:00 | 2026-10-26T00:00:00+00:00 | ALL_BASE                  | BNBUSDT;BTCUSDT;DOGEUSDT;ETHUSDT;PEPEUSDT;SOLUSDT;SUIUSDT;XRPUSDT |           8 |      152 |       -2462.2  |   0.6381 |        -0.2108 |        42.7632 |        30.01 |                  nan |
|      3 | 2026-09-20T00:00:00+00:00 | 2026-10-26T00:00:00+00:00 | ALL_ADX25                 | BNBUSDT;BTCUSDT;DOGEUSDT;ETHUSDT;PEPEUSDT;SOLUSDT;SUIUSDT;XRPUSDT |           8 |      171 |       -2427.24 |   0.6714 |        -0.1753 |        46.7836 |        30.14 |                  nan |
|      3 | 2026-09-20T00:00:00+00:00 | 2026-10-26T00:00:00+00:00 | EXCLUDE_BTC_ETH_SOL_ADX25 | BNBUSDT;DOGEUSDT;PEPEUSDT;SUIUSDT;XRPUSDT                         |           5 |      233 |       -2034.95 |   0.7854 |        -0.1059 |        51.073  |        29.32 |                  nan |
|      3 | 2026-09-20T00:00:00+00:00 | 2026-10-26T00:00:00+00:00 | ONLY_SUI_BNB_ADX25        | SUIUSDT;BNBUSDT                                                   |           2 |      108 |        -170.41 |   0.9606 |        -0.0229 |        53.7037 |        12.02 |                  nan |

## Aggregate diagnostic (sum of independent fold PnLs)
| config                    |   folds_positive |   folds |   trades |   sum_fold_pnl_usdt |   median_fold_pf |   mean_fold_expectancy_r |   median_fold_dd_pct |
|:--------------------------|-----------------:|--------:|---------:|--------------------:|-----------------:|-------------------------:|---------------------:|
| ALL_ADX25                 |                0 |       3 |      474 |            -7669.24 |           0.6714 |                  -0.2417 |                30.18 |
| ALL_BASE                  |                0 |       3 |      499 |            -8373.84 |           0.6381 |                  -0.279  |                30.17 |
| EXCLUDE_BTC_ETH_SOL_ADX25 |                0 |       3 |      508 |            -7072.35 |           0.7587 |                  -0.2245 |                30.31 |
| ONLY_SUI_BNB_ADX25        |                0 |       3 |      291 |            -5296.88 |           0.4266 |                  -0.2471 |                22.6  |

## Per symbol
|   fold | config                    | symbol   |   trades |   net_pnl_usdt |   net_pf |   expectancy_r |
|-------:|:--------------------------|:---------|---------:|---------------:|---------:|---------------:|
|      1 | ALL_BASE                  | BNBUSDT  |       15 |        -245.24 |   0.4085 |        -0.3252 |
|      1 | ALL_BASE                  | BTCUSDT  |       17 |        -617.75 |   0.1889 |        -0.5555 |
|      1 | ALL_BASE                  | DOGEUSDT |       14 |        -486.58 |   0.25   |        -0.4987 |
|      1 | ALL_BASE                  | ETHUSDT  |       13 |        -220.53 |   0.4494 |        -0.2858 |
|      1 | ALL_BASE                  | PEPEUSDT |        8 |        -294.55 |   0.373  |        -0.4489 |
|      1 | ALL_BASE                  | SOLUSDT  |       13 |        -296.94 |   0.5141 |        -0.3328 |
|      1 | ALL_BASE                  | SUIUSDT  |       19 |        -737.9  |   0.262  |        -0.4638 |
|      1 | ALL_BASE                  | XRPUSDT  |        5 |         -48.36 |   0.5641 |        -0.1141 |
|      1 | ALL_ADX25                 | BNBUSDT  |        5 |        -131.17 |   0.2025 |        -0.4606 |
|      1 | ALL_ADX25                 | BTCUSDT  |       16 |        -406.4  |   0.2314 |        -0.4262 |
|      1 | ALL_ADX25                 | DOGEUSDT |       13 |        -445.96 |   0.273  |        -0.4234 |
|      1 | ALL_ADX25                 | ETHUSDT  |       25 |        -601.24 |   0.3356 |        -0.3999 |
|      1 | ALL_ADX25                 | PEPEUSDT |       10 |        -198.04 |   0.6023 |        -0.2092 |
|      1 | ALL_ADX25                 | SOLUSDT  |       13 |         -32.09 |   0.912  |        -0.0392 |
|      1 | ALL_ADX25                 | SUIUSDT  |       16 |        -891.95 |   0.1053 |        -0.6538 |
|      1 | ALL_ADX25                 | XRPUSDT  |       13 |        -312.76 |   0.2146 |        -0.3717 |
|      1 | EXCLUDE_BTC_ETH_SOL_ADX25 | BNBUSDT  |       13 |        -238.62 |   0.3012 |        -0.3555 |
|      1 | EXCLUDE_BTC_ETH_SOL_ADX25 | DOGEUSDT |       19 |        -522.3  |   0.386  |        -0.3385 |
|      1 | EXCLUDE_BTC_ETH_SOL_ADX25 | PEPEUSDT |       15 |        -379.81 |   0.5417 |        -0.311  |
|      1 | EXCLUDE_BTC_ETH_SOL_ADX25 | SUIUSDT  |       22 |       -1173.97 |   0.1414 |        -0.6208 |
|      1 | EXCLUDE_BTC_ETH_SOL_ADX25 | XRPUSDT  |       25 |        -716.34 |   0.2648 |        -0.4474 |
|      1 | ONLY_SUI_BNB_ADX25        | BNBUSDT  |       36 |        -540.48 |   0.401  |        -0.2605 |
|      1 | ONLY_SUI_BNB_ADX25        | SUIUSDT  |       45 |       -1719.24 |   0.3004 |        -0.443  |
|      2 | ALL_BASE                  | BNBUSDT  |       35 |        -176.83 |   0.8392 |        -0.1703 |
|      2 | ALL_BASE                  | BTCUSDT  |       33 |         -45.66 |   0.9514 |        -0.147  |
|      2 | ALL_BASE                  | DOGEUSDT |       36 |         128.38 |   1.1157 |        -0.0183 |
|      2 | ALL_BASE                  | ETHUSDT  |       33 |        -977.11 |   0.3367 |        -0.4544 |
|      2 | ALL_BASE                  | PEPEUSDT |       18 |        -347.01 |   0.6077 |        -0.2037 |
|      2 | ALL_BASE                  | SOLUSDT  |       27 |        -314.96 |   0.7275 |        -0.1759 |
|      2 | ALL_BASE                  | SUIUSDT  |       31 |        -619.43 |   0.578  |        -0.256  |
|      2 | ALL_BASE                  | XRPUSDT  |       30 |        -611.17 |   0.5679 |        -0.3487 |
|      2 | ALL_ADX25                 | BNBUSDT  |       23 |        -348.46 |   0.6525 |        -0.179  |
|      2 | ALL_ADX25                 | BTCUSDT  |       29 |        -129.99 |   0.8711 |        -0.1908 |
|      2 | ALL_ADX25                 | DOGEUSDT |       21 |         128.69 |   1.166  |         0.0481 |
|      2 | ALL_ADX25                 | ETHUSDT  |       25 |       -1026.02 |   0.2714 |        -0.495  |
|      2 | ALL_ADX25                 | PEPEUSDT |       14 |          -0.48 |   0.9992 |         0.0111 |
|      2 | ALL_ADX25                 | SOLUSDT  |       31 |        -219.37 |   0.854  |        -0.0979 |
|      2 | ALL_ADX25                 | SUIUSDT  |       31 |       -1081.75 |   0.3826 |        -0.4029 |
|      2 | ALL_ADX25                 | XRPUSDT  |       18 |         454.99 |   1.7539 |         0.2419 |
|      2 | EXCLUDE_BTC_ETH_SOL_ADX25 | BNBUSDT  |       46 |       -1039.66 |   0.51   |        -0.256  |
|      2 | EXCLUDE_BTC_ETH_SOL_ADX25 | DOGEUSDT |       33 |         242.88 |   1.1945 |         0.0531 |
|      2 | EXCLUDE_BTC_ETH_SOL_ADX25 | PEPEUSDT |       28 |        -411.29 |   0.7003 |        -0.1526 |
|      2 | EXCLUDE_BTC_ETH_SOL_ADX25 | SUIUSDT  |       46 |       -1721.34 |   0.3734 |        -0.421  |
|      2 | EXCLUDE_BTC_ETH_SOL_ADX25 | XRPUSDT  |       28 |         923.05 |   2.1175 |         0.3221 |
|      2 | ONLY_SUI_BNB_ADX25        | BNBUSDT  |       49 |       -1100.81 |   0.4706 |        -0.3015 |
|      2 | ONLY_SUI_BNB_ADX25        | SUIUSDT  |       53 |       -1765.94 |   0.3953 |        -0.4075 |
|      3 | ALL_BASE                  | BNBUSDT  |       29 |        -903.13 |   0.3769 |        -0.4263 |
|      3 | ALL_BASE                  | BTCUSDT  |       23 |        -284.24 |   0.5993 |        -0.1862 |
|      3 | ALL_BASE                  | DOGEUSDT |       21 |         -25.86 |   0.9691 |        -0.0194 |
|      3 | ALL_BASE                  | ETHUSDT  |       18 |        -471.24 |   0.4964 |        -0.3311 |
|      3 | ALL_BASE                  | PEPEUSDT |        9 |        -460.93 |   0.3166 |        -0.5426 |
|      3 | ALL_BASE                  | SOLUSDT  |       18 |        -330.45 |   0.5726 |        -0.2361 |
|      3 | ALL_BASE                  | SUIUSDT  |       16 |         -54.6  |   0.9244 |        -0.0306 |
|      3 | ALL_BASE                  | XRPUSDT  |       18 |          68.25 |   1.0972 |         0.0327 |
|      3 | ALL_ADX25                 | BNBUSDT  |       21 |          39.14 |   1.0617 |         0.0006 |
|      3 | ALL_ADX25                 | BTCUSDT  |       22 |        -464.4  |   0.4039 |        -0.2713 |
|      3 | ALL_ADX25                 | DOGEUSDT |       22 |         -13.48 |   0.984  |        -0.0057 |
|      3 | ALL_ADX25                 | ETHUSDT  |       23 |        -724.85 |   0.4318 |        -0.3665 |
|      3 | ALL_ADX25                 | PEPEUSDT |       12 |        -443.38 |   0.3944 |        -0.4276 |
|      3 | ALL_ADX25                 | SOLUSDT  |       22 |        -614.32 |   0.4396 |        -0.3559 |
|      3 | ALL_ADX25                 | SUIUSDT  |       28 |        -192.96 |   0.8456 |        -0.0848 |
|      3 | ALL_ADX25                 | XRPUSDT  |       21 |         -12.99 |   0.9833 |        -0.006  |
|      3 | EXCLUDE_BTC_ETH_SOL_ADX25 | BNBUSDT  |       48 |        -170.59 |   0.8763 |        -0.0639 |
|      3 | EXCLUDE_BTC_ETH_SOL_ADX25 | DOGEUSDT |       55 |        -411.74 |   0.8071 |        -0.0921 |
|      3 | EXCLUDE_BTC_ETH_SOL_ADX25 | PEPEUSDT |       29 |        -158.33 |   0.871  |        -0.0414 |
|      3 | EXCLUDE_BTC_ETH_SOL_ADX25 | SUIUSDT  |       53 |        -364.86 |   0.8562 |        -0.0675 |
|      3 | EXCLUDE_BTC_ETH_SOL_ADX25 | XRPUSDT  |       48 |        -929.43 |   0.5784 |        -0.2449 |
|      3 | ONLY_SUI_BNB_ADX25        | BNBUSDT  |       49 |        -101.79 |   0.9306 |        -0.0443 |
|      3 | ONLY_SUI_BNB_ADX25        | SUIUSDT  |       59 |         -68.62 |   0.976  |        -0.0051 |

## Caveats
- Each fold restarts capital/state; sum_fold_pnl_usdt is not compounded portfolio return.
- Portfolio simulations use shared capital and max 3 concurrent positions, so results differ from summing independent per-symbol runs.
- A positive result on these folds is not proof of edge; sample size, regime dependence, slippage/funding, and final untouched data remain concerns.