> **Статус на 2026-11-03: PROVISIONAL FOR NET-PNL COMPARISONS.** Эти результаты были получены до исправления exit fee/slippage accounting в v14. TP1/final exit costs ранее рассчитывались от entry notional, а теперь — от qty × modeled execution price. Gross signal results остаются историческими, но net PnL, PF, profitability counts и ranking необходимо пересчитать на исправленном engine. См. `docs/audits/EXCHANGE_SIZING_INTEGRATION_AND_BYBIT_SCHEMA_2026-11-03.md`. Повторный strategy sweep пока заблокирован оставшимися execution/data realism gaps.

# H1 chronological two-period screen — 2026-11-02

## Provenance

- Workflow run: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41424928988
- Workflow name: H1 two-period chronological screen
- Script: scripts/run_h1_two_period_screen.py
- Input: the longest valid archived H1 OHLCV file per symbol from data/archives/cryptofetch/
- No API key, exchange API, or live order was used.
- Baseline engine settings are copied from scripts/run_uploaded_dataset_backtests.py.

## Design

Only symbols with continuous archived coverage across both fixed windows were included. This produces 25 symbols, rather than the full 50-symbol H1 cross-section.

- Screening window: 2025-10-27 00:00 UTC inclusive to 2026-04-29 00:00 UTC exclusive.
- Forward window: 2026-04-29 00:00 UTC inclusive to 2026-10-27 00:00 UTC exclusive.
- Each symbol is replayed independently with 10,000 USDT initial capital, 1% risk/trade, one concurrent position, and the same baseline signal/execution configuration.
- This is a chronological out-of-sample check for symbols selected only on the first window, provided the first-window candidate set is frozen before examining the forward outcomes.

## Aggregate result

| Window | Symbols | Trades | Profitable symbols | Sum of independent net PnL | Median net PF |
|---|---:|---:|---:|---:|---:|
| Screening | 25 | 1,752 | 9 / 25 | -1,886.09 USDT | 0.95 |
| Forward | 25 | 1,777 | 6 / 25 | -14,789.82 USDT | 0.82 |

These sums combine independent 10,000-USDT tests and are not a shared-capital portfolio PnL.

## Positive screening-period symbols and their forward results

| Symbol | Screening net, USDT | Screening PF | Forward trades | Forward net, USDT | Forward PF |
|---|---:|---:|---:|---:|---:|
| WLDUSDT | 2,414.34 | 1.73 | 51 | -101.92 | 0.96 |
| DASHUSDT | 2,261.59 | 2.16 | 66 | -253.50 | 0.92 |
| ENAUSDT | 1,104.32 | 1.42 | 53 | -1,133.27 | 0.63 |
| ONDOUSDT | 643.56 | 1.17 | 70 | -983.17 | 0.73 |
| RAYUSDT | 436.13 | 1.13 | 68 | 108.90 | 1.03 |
| HBARUSDT | 131.77 | 1.03 | 88 | -441.53 | 0.91 |
| AAVEUSDT | 106.78 | 1.03 | 71 | 217.08 | 1.06 |
| GMXUSDT | 21.21 | 1.01 | 77 | -892.68 | 0.79 |
| CAKEUSDT | 20.40 | 1.00 | 88 | -240.25 | 0.95 |

Only AAVEUSDT and RAYUSDT remained net positive in the later window among the nine screening-period winners. Their forward edges are weak (PF 1.06 and 1.03), so neither is validated as robust.

## Forward-period positive symbols

| Symbol | Trades | Net PnL, USDT | Net PF | Expectancy, R/trade | Max DD |
|---|---:|---:|---:|---:|---:|
| BCHUSDT | 78 | 1,360.68 | 1.35 | 0.1714 | 8.90% |
| PUMPUSDT | 39 | 1,261.19 | 1.76 | 0.3137 | 4.41% |
| TAOUSDT | 66 | 1,015.26 | 1.34 | 0.1536 | 12.26% |
| DOTUSDT | 71 | 300.85 | 1.09 | 0.0483 | 9.42% |
| AAVEUSDT | 71 | 217.08 | 1.06 | 0.0367 | 6.75% |
| RAYUSDT | 68 | 108.90 | 1.03 | 0.0231 | 9.94% |

## Interpretation

1. The broad full-sample 14/50 positive count materially overstates stability. The chronological screen shows only 9/25 positive in the first window and 6/25 in the later window.
2. Most first-window winners failed to retain positive expectancy in the later window. Only AAVE and RAY stayed slightly positive, with very small forward PF margins.
3. The forward winners differ substantially from the screening winners (BCH, PUMP, TAO, DOT were not first-window winners). This is evidence of time-varying instrument/strategy fit, not evidence that selecting these later winners will work prospectively.
4. The forward aggregate remains strongly negative and median PF falls to 0.82. The current baseline strategy is not suitable for deployment on this evidence.
5. This experiment still uses Binance OHLCV proxy data, modeled fees/slippage, and no historical funding/mark-price data. It does not model exact Bybit fills, order-book queue, partial fills, maintenance margin, or liquidation.

## Decision

Do not optimize the strategy around the 14 full-sample winners or switch live trading to the six forward winners. Freeze this experiment as a negative robustness result. The next research question should be why the same symbols and unchanged rules flip across the two windows, with period-level market regime and trade-level loss attribution. Any new filter must be causal, pre-specified, and evaluated on a later untouched period.
