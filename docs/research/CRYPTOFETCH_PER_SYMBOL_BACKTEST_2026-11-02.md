# CryptoFetch per-symbol backtest — 2026-11-02

## Run provenance

- Branch: research/market-regime-v1-main
- Workflow: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41424607051
- Workflow run: 41424607051 — completed successfully
- Commit: bc1704092a3cd86e3aa3ff55f7a08d73a7e7bc64
- Script: scripts/run_uploaded_dataset_backtests.py
- Artifact: cryptofetch-per-symbol-backtest-results (artifact ID 13130897723)
- Input: committed ZIP archives under data/archives/cryptofetch/
- No exchange API, API key, or live order was used.

## Aggregate result

| Timeframe | Symbols | Trades | Profitable symbols after modeled costs | Sum of independent net PnL |
|---|---:|---:|---:|---:|
| 1h | 50 | 5,254 | 14 / 50 | -23,231.98 USDT |
| 15m | 8 | 1,221 | 0 / 8 | -22,299.67 USDT |

Each symbol is tested independently with 10,000 USDT initial capital, 1% risk per trade, and one concurrent position. The summed PnL is a diagnostic sum of isolated runs, not a shared-capital portfolio result.

## H1 symbols with positive net PnL

| Symbol | Trades | Gross PnL, USDT | Modeled costs, USDT | Net PnL, USDT | Net PF | Expectancy, R/trade | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| WLDUSDT | 116 | 2,884.52 | 662.55 | 2,221.97 | 1.35 | 0.1814 | 9.39% |
| ZECUSDT | 55 | 2,452.27 | 311.04 | 2,141.23 | 1.82 | 0.3620 | 4.91% |
| DASHUSDT | 118 | 2,596.22 | 748.61 | 1,847.61 | 1.31 | 0.1508 | 9.52% |
| XRPUSDT | 86 | 1,499.89 | 861.64 | 638.25 | 1.14 | 0.0789 | 6.80% |
| UNIUSDT | 63 | 981.66 | 358.84 | 622.82 | 1.19 | 0.1041 | 7.68% |
| RAYUSDT | 128 | 1,360.34 | 810.56 | 549.78 | 1.08 | 0.0498 | 12.19% |
| PUMPUSDT | 92 | 933.52 | 395.80 | 537.72 | 1.12 | 0.0649 | 17.38% |
| GRAMUSDT | 47 | 828.54 | 384.89 | 443.65 | 1.18 | 0.1002 | 6.34% |
| AAVEUSDT | 140 | 1,248.51 | 832.04 | 416.47 | 1.05 | 0.0372 | 10.41% |
| SUIUSDT | 60 | 796.42 | 408.26 | 388.16 | 1.12 | 0.0716 | 13.34% |
| BCHUSDT | 150 | 1,422.28 | 1,156.01 | 266.27 | 1.04 | 0.0248 | 15.06% |
| PEPEUSDT | 44 | 459.08 | 226.08 | 233.00 | 1.11 | 0.0595 | 6.30% |
| HYPEUSDT | 16 | 243.47 | 121.06 | 122.41 | 1.17 | 0.0821 | 3.37% |
| ADAUSDT | 77 | 532.28 | 497.10 | 35.18 | 1.01 | 0.0116 | 10.06% |

## Data coverage and caveats

- Six ZIP archives were inventoried: 67 CSV entries. The CSV schemas inspected are Binance-style OHLCV (open_time_ms, OHLC, volume, and trade/quote-volume fields).
- The archives contain no separate funding-history CSVs and no separate mark-price datasets. This backtest script does not pass historical funding events to the engine. Therefore results are net of the engine's modeled exchange fees and slippage, but not proven net of historical funding.
- Market candles are Binance OHLCV proxies, not Bybit execution candles. Maker/taker fills, order-book queue, latency, partial fills, adverse selection, exact Bybit tick/qty constraints, liquidation and maintenance margin are not established by this run.
- Coverage is unequal: some H1 instruments have a full 2025-10-27 to 2026-10-27 year; many have only 2026-04-29 to 2026-10-26; GRAM begins 2026-07-02; HYPE has only 758 bars from 2026-09-24 to 2026-10-26. Positive results with short histories and small trade counts are especially fragile.
- The 15m data covers only eight instruments from 2026-04-29 to 2026-10-26. All eight are net negative in this run.
- The script chooses the longest valid file per symbol/timeframe; duplicate datasets are resolved by bar count and archive-name ordering. It skips empty DAIUSDT, MATICUSDT and XMRUSDT files.
- Per-symbol independent tests do not model capital competition across symbols and do not demonstrate a tradable top-5 portfolio.

## Interpretation and next validation

This is a screening result, not a strategy approval. Fourteen H1 instruments are positive under this exact engine/configuration/cost model, but the aggregate H1 sample is deeply negative and the median symbol PF is 0.93. The positive names must not be selected and optimized on the same full period without an untouched holdout.

Next:
1. Freeze the current baseline and candidate list before further tuning.
2. Re-test positive candidates on common, date-aligned periods; report results separately for the 2025-10-27 to 2026-04-29 and 2026-04-29 to 2026-10-26 windows where data permits.
3. Separate selection from validation: use one period for screening, another for candidate selection, and an untouched holdout for final evaluation.
4. Build a shared-capital replay for a small candidate basket, with the same risk budget, position limits and deterministic signal priority.
5. Obtain lawful, permitted historical funding and mark-price data and Bybit instrument-spec history before treating the result as exchange-realistic.
6. Stress fees, slippage, fill assumptions, gaps and funding; reject candidates whose edge disappears under modest adverse execution assumptions.

No strategy parameters were changed by this report.
