# Первый предварительный бэктест BTCUSDT H1 — 2026-11-25

## Итог

Выполнен первый предварительный Bybit-only OHLCV replay на официальном публичном архиве Bybit.

- GitHub Actions run: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45656943072
- Commit: `fe176011a9b108dd52caee194d2384e7d2c4bb22`
- Artifact: `preliminary-bybit-btc-h1-backtest` (ID `15043716406`)
- Данные: 47,085 H1 bars, 2020-04-01 00:00 UTC — 2025-11-03 04:00 UTC.
- 4 gaps, 1,928 missing hourly bars; no synthetic candles. Gaps split history into 5 independent contiguous segments.
- 27 runs: 3 arms × 3 out-of-sample folds × 3 cost multipliers.
- 2,262 closed trades across all variants.

## Предварительные результаты

Начальный капитал каждой независимой fold-run: 10,000 USDT. Риск: 1% equity per trade; одна позиция одновременно; long-only. Порог объёма фиксирован 1.6. Комиссия taker 5.5 bps + slippage 2.25 bps per side; costs stress 1x/1.5x/2x.

| Fold | Arm | Costs | Trades | Net PnL, USDT | Return | PF | Closed-trade DD | Expectancy R |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | A_D20 | 1x | 110 | -1875.11 | -18.75% | 0.768 | 27.45% | -0.1778 |
| 1 | A_D20 | 1.5x | 110 | -2570.10 | -25.70% | 0.692 | 32.08% | -0.2587 |
| 1 | A_D20 | 2x | 110 | -3206.44 | -32.06% | 0.626 | 36.42% | -0.3396 |
| 1 | B_D48 | 1x | 65 | -229.02 | -2.29% | 0.951 | 15.24% | -0.0237 |
| 1 | B_D48 | 1.5x | 65 | -632.33 | -6.32% | 0.869 | 17.15% | -0.0885 |
| 1 | B_D48 | 2x | 65 | -1019.32 | -10.19% | 0.797 | 19.02% | -0.1532 |
| 1 | C_D48_EMA | 1x | 35 | 1029.62 | 10.30% | 1.466 | 7.65% | 0.2934 |
| 1 | C_D48_EMA | 1.5x | 35 | 822.92 | 8.23% | 1.357 | 8.07% | 0.2393 |
| 1 | C_D48_EMA | 2x | 35 | 619.97 | 6.20% | 1.259 | 8.50% | 0.1851 |
| 2 | A_D20 | 1x | 116 | 329.11 | 3.29% | 1.043 | 21.39% | 0.0375 |
| 2 | A_D20 | 1.5x | 116 | -317.74 | -3.18% | 0.959 | 24.05% | -0.0183 |
| 2 | A_D20 | 2x | 116 | -924.49 | -9.24% | 0.881 | 26.68% | -0.0742 |
| 2 | B_D48 | 1x | 71 | 330.05 | 3.30% | 1.079 | 6.92% | 0.0547 |
| 2 | B_D48 | 1.5x | 71 | -28.39 | -0.28% | 0.993 | 8.65% | 0.0050 |
| 2 | B_D48 | 2x | 71 | -374.60 | -3.75% | 0.916 | 10.36% | -0.0447 |
| 2 | C_D48_EMA | 1x | 43 | 401.84 | 4.02% | 1.182 | 5.49% | 0.0996 |
| 2 | C_D48_EMA | 1.5x | 43 | 184.62 | 1.85% | 1.080 | 5.88% | 0.0506 |
| 2 | C_D48_EMA | 2x | 43 | -28.18 | -0.28% | 0.988 | 6.27% | 0.0015 |
| 3 | A_D20 | 1x | 139 | 460.79 | 4.61% | 1.057 | 12.25% | 0.0410 |
| 3 | A_D20 | 1.5x | 139 | -415.08 | -4.15% | 0.950 | 14.38% | -0.0219 |
| 3 | A_D20 | 2x | 139 | -1218.22 | -12.18% | 0.855 | 19.11% | -0.0849 |
| 3 | B_D48 | 1x | 102 | -453.94 | -4.54% | 0.926 | 15.57% | -0.0364 |
| 3 | B_D48 | 1.5x | 102 | -1022.02 | -10.22% | 0.839 | 18.05% | -0.0966 |
| 3 | B_D48 | 2x | 102 | -1556.67 | -15.57% | 0.761 | 20.77% | -0.1567 |
| 3 | C_D48_EMA | 1x | 73 | -45.48 | -0.45% | 0.990 | 12.94% | 0.0039 |
| 3 | C_D48_EMA | 1.5x | 73 | -497.53 | -4.98% | 0.898 | 15.04% | -0.0597 |
| 3 | C_D48_EMA | 2x | 73 | -929.38 | -9.29% | 0.816 | 17.10% | -0.1234 |

## Протокол вариантов

- A_D20: Donchian 20, volume lookback 20, EMA gate off.
- B_D48: Donchian 48, volume lookback 48, EMA gate off.
- C_D48_EMA: Donchian 48, volume lookback 48, EMA50 > EMA200, EMA200 rising vs 5 bars earlier, close > EMA200.
- Signal on closed candle, entry at next candle open.
- Stop 2.5 ATR(14), TP1 2R at 50%, TP2 5R remaining, ATR(14)×3 trailing after TP1, time exit 32 bars.
- Intrabar ambiguity handled stop-first. Trailing update is close-derived and delayed, not lookahead.

## Interpretation

- Candidate C was positive in fold 1 at all cost levels: +10.30% at 1x, +8.23% at 1.5x, +6.20% at 2x.
- Fold 2 C weakened materially: +4.02%, +1.85%, -0.28%.
- Confirm fold 3 C was negative even at 1x: -0.45%, -4.98%, -9.29%.
- Therefore the initial attractive fold-1 result does **not** persist in the final confirm fold. This run does not establish a robust edge.
- D20 and D48 controls also failed to show robust profitability under costs.

## Limitations — not production PnL

This deliberately permissive preliminary test uses Bybit trade OHLCV only. It excludes:
- Funding payments;
- Mark-price based liquidation and margin accounting;
- dated instrument tick/lot specs and historical risk tiers;
- maker queue, spread, partial fills and adverse selection;
- portfolio concurrency across symbols.

It assumes taker execution at next H1 open, explicit taker fees and fixed slippage. It is a diagnostic screening run, not an execution-faithful replay. It is not evidence of a live-tradable edge.

## Raw result CSV

```csv
fold,arm,cost_multiplier,trades,net_pnl_usdt,return_pct,profit_factor,max_drawdown_closed_trade_pct,expectancy_r,costs_usdt
1,A_D20,1,110,-1875.11,-18.75,0.768,27.45,-0.1778,1747.45
1,A_D20,1.5,110,-2570.1,-25.7,0.692,32.08,-0.2587,2512.84
1,A_D20,2,110,-3206.44,-32.06,0.626,36.42,-0.3396,3213.84
1,B_D48,1,65,-229.02,-2.29,0.951,15.24,-0.0237,894.08
1,B_D48,1.5,65,-632.33,-6.32,0.869,17.15,-0.0885,1313.89
1,B_D48,2,65,-1019.32,-10.19,0.797,19.02,-0.1532,1716.5
1,C_D48_EMA,1,35,1029.62,10.3,1.466,7.65,0.2934,417.76
1,C_D48_EMA,1.5,35,822.92,8.23,1.357,8.07,0.2393,620.84
1,C_D48_EMA,2,35,619.97,6.2,1.259,8.5,0.1851,820.14
2,A_D20,1,116,329.11,3.29,1.043,21.39,0.0375,1462.67
2,A_D20,1.5,116,-317.74,-3.18,0.959,24.05,-0.0183,2125.06
2,A_D20,2,116,-924.49,-9.24,0.881,26.68,-0.0742,2745.21
2,B_D48,1,71,330.05,3.3,1.079,6.92,0.0547,734.28
2,B_D48,1.5,71,-28.39,-0.28,0.993,8.65,0.005,1082.24
2,B_D48,2,71,-374.6,-3.75,0.916,10.36,-0.0447,1418
2,C_D48_EMA,1,43,401.84,4.02,1.182,5.49,0.0996,434.6
2,C_D48_EMA,1.5,43,184.62,1.85,1.08,5.88,0.0506,645.14
2,C_D48_EMA,2,43,-28.18,-0.28,0.988,6.27,0.0015,851.3
3,A_D20,1,139,460.79,4.61,1.057,12.25,0.041,1820.72
3,A_D20,1.5,139,-415.08,-4.15,0.95,14.38,-0.0219,2615.69
3,A_D20,2,139,-1218.22,-12.18,0.855,19.11,-0.0849,3342.23
3,B_D48,1,102,-453.94,-4.54,0.926,15.57,-0.0364,1202.25
3,B_D48,1.5,102,-1022.02,-10.22,0.839,18.05,-0.0966,1750.48
3,B_D48,2,102,-1556.67,-15.57,0.761,20.77,-0.1567,2266.15
3,C_D48_EMA,1,73,-45.48,-0.45,0.99,12.94,0.0039,936.52
3,C_D48_EMA,1.5,73,-497.53,-4.98,0.898,15.04,-0.0597,1373.37
3,C_D48_EMA,2,73,-929.38,-9.29,0.816,17.1,-0.1234,1790.51
```
