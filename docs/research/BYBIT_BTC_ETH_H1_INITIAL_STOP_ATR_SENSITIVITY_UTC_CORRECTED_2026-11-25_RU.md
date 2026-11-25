# BTC/ETH H1 — initial stop ATR sensitivity (UTC-normalized data)

Date: 2026-11-25  
Branch: research/h1-volume-lookback-provenance-fix

## Data correction

The Bybit MT4 H1 archive timestamps were found to be consistently +3 hours versus UTC. The downloader now subtracts 3 hours and writes normalized UTC timestamps. The offset was validated against Bybit public trade volumes on 12 dates across 2020-2025, including winter and summer samples. After correction, 288 hourly buckets aligned with best offset 0; median absolute volume difference was 0%, p95 0.3028%, maximum 3.1253%.

This report uses the corrected loader output. Price and volume values and bar order are unchanged; calendar timestamps are corrected.

## Method

- BTCUSDT and ETHUSDT linear H1, official Bybit archives only.
- Fixed Arm C: Donchian 48, EMA50 > EMA200, EMA200 rising over 5 bars, close > EMA200.
- Volume ratio threshold 1.6, lookback 48.
- Initial stop: 2.5 / 3.0 / 3.5 ATR.
- TP1 2R / 50%; TP2 5R; ATR×3 trailing after TP1; time exit 32 bars.
- Risk 1% per trade; 10,000 USDT starting capital.
- Costs: 1x / 1.5x / 2x original modeled taker fee + slippage.
- 54 configurations, 2 symbols × 3 folds × 3 stop distances × 3 cost multipliers; 2,313 trade rows.

## BTCUSDT results

Net PnL summed across the three chronological folds (not compounded):

| Initial stop | Trades | Costs 1x | Costs 1.5x | Costs 2x |
|---|---:|---:|---:|---:|
| 2.5 ATR | 151 | +1,385.98 | +510.01 | -337.59 |
| 3.0 ATR | 149 | +1,686.02 | +954.20 | +241.87 |
| 3.5 ATR | 143 | **+1,781.51** | **+1,169.16** | **+570.50** |

Fold-level results for the 3.5 ATR stop:
- Fold 1: +652.41 / +516.85 / +382.94 USDT at 1x / 1.5x / 2x.
- Fold 2: +1,083.00 / +921.93 / +763.15 USDT.
- Fold 3: +46.10 / -269.62 / -575.59 USDT.

The aggregate ranking is unchanged: 3.5 ATR is strongest on this historical sample. But it is not robust in the third fold under elevated costs. This is not sufficient evidence to promote it to a production parameter.

## ETHUSDT fixed-parameter replication

| Initial stop | Trades | Costs 1x | Costs 1.5x | Costs 2x |
|---|---:|---:|---:|---:|
| 2.5 ATR | 112 | +756.47 | +303.71 | -142.54 |
| 3.0 ATR | 108 | +723.10 | +358.37 | -2.10 |
| 3.5 ATR | 108 | +483.70 | +173.65 | -133.31 |

ETH does not confirm a general benefit from wider stops.

## Same-window BTC/ETH check

The corrected timestamp loader was also used to rerun the fixed BTC-vs-ETH comparison on the same calendar window (2024-04-11 13:00 UTC to 2024-12-12 02:00 UTC). Results matched the previous same-window values to reported precision:
- BTC, 41 trades: +41.66 USDT at 1x, -140.39 at 1.5x, -319.22 at 2x.
- ETH, 34 trades: -375.25 USDT at 1x, -491.88 at 1.5x, -607.15 at 2x.

## Decision

- Keep 3.0 and 3.5 ATR as research candidates only.
- Do not select 3.5 ATR solely because it wins on aggregate PnL.
- Do not add new stop-size tuning until trade-flow and orderbook data are integrated and independently tested.
- No real-money deployment.

## Reproduction

- Corrected sensitivity run: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45671263007
- Corrected same-window run: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45671263022
- Timestamp audit: docs/research/BYBIT_H1_TIMESTAMP_ALIGNMENT_AUDIT_2026-11-25_RU.md

## Limitations

Still an OHLCV-only model: no funding, mark-price execution, liquidation engine, historical instrument/risk-tier snapshots in this runner, bid/ask spread, queue position, or market impact. These results are research diagnostics, not a validated trading edge.
