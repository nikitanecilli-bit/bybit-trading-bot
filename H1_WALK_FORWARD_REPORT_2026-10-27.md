# H1 walk-forward validation — 2026-10-27

## Method

- Input: uploaded CryptoFetch archives containing Binance OHLCV candles.
- H1 only; each symbol runs independently from 10,000 USDT.
- Same baseline parameters as `scripts/run_uploaded_dataset_backtests.py`.
- Chronological split: first 70% train, final 30% holdout.
- Train candidate criteria are defined in advance: at least 30 trades, net PnL > 0, PF > 1, expectancy > 0R.
- Holdout uses a fresh engine and starts flat. No parameters were tuned in this test.
- This is a first screening pass, not proof of statistical significance. Holdout period is only around the final 30% of this ~6-month sample and some symbols have fewer trades.

## Result

25 H1 symbols had valid datasets. 7 met the train-only candidate criteria; 3 of those also had positive holdout net PnL, PF > 1 and positive expectancy with at least 10 holdout trades:

| Symbol | Train trades | Train net PnL | Train PF | Holdout trades | Holdout net PnL | Holdout PF | Holdout expectancy (R) | Holdout max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TAOUSDT | 50 | +190.05 | 1.08 | 16 | +769.21 | 2.36 | +0.4716 | 3.55% |
| UNIUSDT | 49 | +574.81 | 1.23 | 14 | +45.38 | 1.06 | +0.0389 | 2.90% |
| ZECUSDT | 38 | +2,071.88 | 2.46 | 16 | +159.03 | 1.18 | +0.1081 | 4.33% |

All figures are independent single-symbol runs, not a combined portfolio. Results are after modeled fees/slippage. Note the small holdout trade counts: 14–16 trades is weak evidence and could be luck.

### Train-positive candidates that failed holdout

| Symbol | Train net PnL | Train PF | Holdout net PnL | Holdout PF |
|---|---:|---:|---:|---:|
| LTCUSDT | +155.05 | 1.07 | −150.56 | 0.88 |
| PEPEUSDT | +262.83 | 1.18 | −29.11 | 0.96 |
| SOLUSDT | +463.53 | 1.15 | −658.83 | 0.59 |
| XRPUSDT | +1,039.59 | 1.38 | −267.75 | 0.83 |

This is a useful demonstration of why filtering on the full-sample report alone is unsafe: several apparently profitable assets did not hold up chronologically.

## Selected full result table

| Symbol | Train trades | Train net | Train PF | Train expectancy R | Train max DD | Holdout trades | Holdout net | Holdout PF | Holdout expectancy R | Holdout max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| AAVEUSDT | 49 | −1.91 | 1.00 | +0.0062 | 6.75% | 20 | +309.01 | 1.36 | +0.1586 | 4.99% |
| ADAUSDT | 58 | −328.30 | 0.89 | −0.0502 | 10.06% | 19 | +375.77 | 1.48 | +0.2001 | 3.20% |
| ALGOUSDT | 46 | −974.03 | 0.63 | −0.2168 | 10.93% | 15 | +541.86 | 2.17 | +0.3573 | 2.04% |
| APTUSDT | 49 | −957.23 | 0.65 | −0.1997 | 16.12% | 13 | −99.84 | 0.85 | −0.0692 | 3.47% |
| ARBUSDT | 46 | −1,384.67 | 0.51 | −0.3171 | 21.67% | 6 | −70.24 | 0.79 | −0.1118 | 3.45% |
| ATOMUSDT | 61 | −578.29 | 0.83 | −0.0908 | 8.13% | 21 | +690.50 | 1.97 | +0.3238 | 2.59% |
| AVAXUSDT | 60 | −856.48 | 0.74 | −0.1431 | 9.77% | 20 | +562.85 | 1.57 | +0.2822 | 4.20% |
| BNBUSDT | 66 | −763.53 | 0.79 | −0.1140 | 14.59% | 31 | −69.49 | 0.96 | −0.0162 | 6.90% |
| BTCUSDT | 79 | −1,503.49 | 0.64 | −0.2004 | 17.61% | 30 | −407.27 | 0.76 | −0.1319 | 10.31% |
| DOGEUSDT | 65 | −1,974.83 | 0.45 | −0.3333 | 24.23% | 23 | +1,122.10 | 2.24 | +0.4721 | 3.31% |
| DOTUSDT | 56 | −150.03 | 0.95 | −0.0209 | 9.42% | 13 | +670.08 | 2.55 | +0.5078 | 2.38% |
| ETHUSDT | 66 | −451.97 | 0.87 | −0.0635 | 11.80% | 30 | +88.24 | 1.06 | +0.0359 | 7.89% |
| LINKUSDT | 55 | −696.55 | 0.77 | −0.1245 | 12.96% | 24 | +15.31 | 1.01 | +0.0137 | 6.16% |
| LTCUSDT | 49 | +155.05 | 1.07 | +0.0374 | 6.72% | 22 | −150.56 | 0.88 | −0.0618 | 5.00% |
| MINAUSDT | 42 | −576.61 | 0.77 | −0.1332 | 11.72% | 10 | +290.60 | 1.71 | +0.2945 | 2.74% |
| NEARUSDT | 47 | −1,090.11 | 0.60 | −0.2396 | 12.98% | 10 | −209.10 | 0.69 | −0.2015 | 3.84% |
| PEPEUSDT | 31 | +262.83 | 1.18 | +0.0908 | 5.79% | 13 | −29.11 | 0.96 | −0.0151 | 6.30% |
| POLUSDT | 55 | −472.59 | 0.84 | −0.0809 | 8.27% | 15 | −368.62 | 0.63 | −0.2438 | 4.16% |
| SOLUSDT | 62 | +463.53 | 1.15 | +0.0804 | 6.95% | 27 | −658.83 | 0.59 | −0.2467 | 10.21% |
| SUIUSDT | 44 | −573.94 | 0.79 | −0.1262 | 13.34% | 16 | +706.67 | 2.28 | +0.4341 | 2.91% |
| TAOUSDT | 50 | +190.05 | 1.08 | +0.0442 | 12.26% | 16 | +769.21 | 2.36 | +0.4716 | 3.55% |
| TRXUSDT | 82 | −266.11 | 0.94 | −0.0267 | 13.10% | 39 | −1,057.51 | 0.52 | −0.2821 | 12.00% |
| UNIUSDT | 49 | +574.81 | 1.23 | +0.1227 | 7.68% | 14 | +45.38 | 1.06 | +0.0389 | 2.90% |
| XRPUSDT | 62 | +1,039.59 | 1.38 | +0.1660 | 5.52% | 24 | −267.75 | 0.83 | −0.1046 | 6.82% |
| ZECUSDT | 38 | +2,071.88 | 2.46 | +0.5048 | 4.91% | 16 | +159.03 | 1.18 | +0.1081 | 4.33% |

## Recommendation

- Keep H1 as the primary research timeframe and stop spending effort on the current 15m configuration.
- Do not permanently delete assets yet. Keep a research universe and a separate candidate pool.
- TAO, UNI and ZEC are the only symbols that passed this initial train-to-holdout screen, but the sample is too small to promote them to live trading.
- Next: extend data history, perform rolling walk-forward tests, stress costs/slippage, and only then evaluate parameter changes on candidates. Avoid optimizing many parameter combinations against this same holdout.
- Data caveat: the files are Binance OHLCV, not Bybit; results are a proxy for the Bybit execution model.
