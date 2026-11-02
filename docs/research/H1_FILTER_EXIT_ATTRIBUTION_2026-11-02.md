> **Статус на 2026-11-03: PROVISIONAL FOR NET-PNL COMPARISONS.** Эти результаты были получены до исправления exit fee/slippage accounting в v14. TP1/final exit costs ранее рассчитывались от entry notional, а теперь — от qty × modeled execution price. Gross signal results остаются историческими, но net PnL, PF, profitability counts и ranking необходимо пересчитать на исправленном engine. См. `docs/audits/EXCHANGE_SIZING_INTEGRATION_AND_BYBIT_SCHEMA_2026-11-03.md`. Повторный strategy sweep пока заблокирован оставшимися execution/data realism gaps.

# H1 filter exit attribution — 2026-11-02

## Run

- Workflow: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41429608510
- Branch: `research/market-regime-v1-main`
- Commit: `11c9235364b627a613fcca3e89384f2e1e81827d`
- Result: success; artifact `h1-filter-exit-attribution`.
- Research-only script: `scripts/analyze_h1_filter_exit_attribution.py`.
- No production engine or live trading config changes.

## Method

Same 25 full-year H1 symbols, two fixed windows, per-symbol independent runs, 10,000 USDT start capital, 1% risk/trade, same engine and modeled costs:
- Screening: 2025-10-27 00:00 UTC — 2026-04-29 00:00 UTC.
- Forward: 2026-04-29 00:00 UTC — 2026-10-27 00:00 UTC.

Compared:
- Baseline.
- Strict actual-entry US block: exclude a signal if the next H1 candle (the entry candle) opens in US session.
- Prior-24h directional alignment + strict actual-entry US block.

Aggregates are sums of independent symbol runs, not shared-capital portfolio returns.

## Summary

| Period | Variant | Trades | Net PnL | Gross PnL | Fees | Slippage | Winning trades |
|---|---|---:|---:|---:|---:|---:|---:|
| Screening | Baseline | 1,752 | -1,886.09 | 10,612.34 | 8,869.99 | 3,628.44 | 690 |
| Screening | Actual-entry US block | 1,236 | +7,440.00 | 16,898.32 | 6,712.32 | 2,746.00 | 509 |
| Screening | Alignment + actual-entry US block | 1,119 | +8,543.31 | 17,045.23 | 6,033.70 | 2,468.22 | 469 |
| Forward | Baseline | 1,777 | -14,789.82 | -1,303.17 | 9,571.00 | 3,915.65 | 681 |
| Forward | Actual-entry US block | 1,378 | -5,341.50 | 5,492.40 | 7,688.71 | 3,145.19 | 548 |
| Forward | Alignment + actual-entry US block | 1,240 | -2,819.98 | 6,920.68 | 6,912.75 | 2,827.91 | 503 |

## What the filter actually removes

Forward baseline exit reasons:
- Stop loss: 926 trades, -88,961.33 USDT.
- Time stop: 558 trades, +28,794.92 USDT.
- Trailing stop: 240 trades, +32,218.06 USDT.
- Take profit: 46 trades, +13,213.81 USDT.

Forward strict actual-entry US block:
- Stop loss: 699 trades, -68,367.87 USDT.
- Time stop: 444 trades, +25,875.29 USDT.
- Trailing stop: 194 trades, +26,939.83 USDT.
- Take profit: 36 trades, +10,215.52 USDT.

It removed 399 trades: 227 stop-loss trades, 114 time-stop trades, 46 trailing-stop trades and 10 take-profit trades (end-of-test/kill-switch details are separate). Thus the net improvement is not explained only by removing losing stops: it also removes profitable time-stop, trailing and target trades. The net gain is consistent with avoiding a particularly poor entry cohort, but does not prove the underlying market mechanism.

## Session and direction breakdown

Forward baseline:
- Asia: 540 trades, -2,975.21 USDT.
- Europe: 704 trades, -1,134.20 USDT.
- US: 533 trades, -10,680.41 USDT.

After strict US-entry block:
- Asia: 620 trades, -2,785.47 USDT.
- Europe: 758 trades, -2,556.03 USDT.
- No US entries.

This confirms US entry cohort is the worst segment in the baseline, but removing it does not make the remaining sessions profitable.

After alignment + strict US-entry block:
- Asia: 570 trades, -3,869.48 USDT.
- Europe: 670 trades, +1,049.50 USDT.
- Longs: 632 trades, +3,474.03 USDT.
- Shorts: 608 trades, -6,294.01 USDT.

The combined rule's remaining forward loss is concentrated in Asia and especially short positions. This is a diagnostic observation on the same already-inspected windows, not an invitation to add another filter and retune against this holdout.

## Screening vs forward

The session exclusion effect is present in both windows:
- Screening net improves from -1,886.09 to +7,440.00 USDT.
- Forward net improves from -14,789.82 to -5,341.50 USDT.

But the non-US cohort changes materially: screening Asia +4,336.82 and Europe +3,103.18; forward Asia -2,785.47 and Europe -2,556.03. Therefore "trade only Asia/Europe" is not a stable profitable rule across these periods. The market regime within those sessions changed.

## Interpretation and limits

1. The US-entry cohort was strongly negative in both the baseline attribution and the strict boundary test, so session timing is a meaningful explanatory variable.
2. The filter's benefit is largely associated with removing a high-loss cohort, but it also removes some positive trades; it is not a free reduction in losses.
3. The remaining Asia/Europe cohort is negative in the forward period. Session exclusion alone is not sufficient.
4. The prior-24h alignment condition shifts the forward result toward break-even but remains negative and is highly asymmetric: longs positive, shorts negative. Do not tune direction-specific rules on these same windows.
5. The test is not independent validation. The filters were explored after seeing these two periods; use only as hypothesis generation.
6. OHLCV data and modeled fees/slippage do not reproduce Bybit order book, queue position, partial fills, latency, funding or liquidation.

## Time filters audit

The config fields `blocked_signal_hours_utc` and `blocked_weekdays_utc` are explicitly named and implemented as signal-time gates in `evaluate_signal()`. They are not currently used by this research experiment. Their semantics should remain explicit: if the desired business rule is "no signal generated at these hours/days", current behavior is consistent with the names; if the intended rule is "no actual entry at these hours/days", they need a separate next-entry-candle check. No production changes were made.

## Decision

No strategy or filter is approved for live use. Keep the strict actual-entry timestamp semantics for future research. The next valid step is a preregistered holdout on new data, not more parameter tuning on these same two periods.
