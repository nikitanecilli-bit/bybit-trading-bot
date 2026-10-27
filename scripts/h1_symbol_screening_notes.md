# H1 symbol shortlist — research only

The shortlist uses two constraints: (1) results across the prior H1 signal-quality matrix, and (2) enough shared candle history to compare the June 21–August 15, 2026 regime across instruments on the same dates. High-scoring symbols with only about three months of available data remain in a separate watchlist rather than shrinking the common-period portfolio test.

## Primary candidates (5; common-history group)
1. RAYUSDT
2. PUMPUSDT
3. TAOUSDT
4. AAVEUSDT
5. CAKEUSDT

## Reserve candidates — hybrid regime test (5)
1. DASHUSDT
2. HBARUSDT
3. ENAUSDT
4. GMXUSDT
5. ONDOUSDT

The previous reserve basket DASH/ENA/HBAR/ASTER/JST was positive in all 12 configurations on folds 1 and 3 but negative in all 12 on fold 2. The alternative ENA/GMX/ONDO/SKY/QNT basket improved the middle fold (7/12 positive at 2x modeled costs) but lost on fold 1 in all 12 configurations. This hybrid retains DASH and HBAR for the first/last folds and adds ENA, GMX, ONDO, which showed some middle-fold resilience. It is an experiment, not a claim of profitability.

## High-scoring shorter-history watchlist
- LINKUSDT
- APTUSDT
- POLUSDT
- ATOMUSDT
- DOGEUSDT

These shorter-history candidates should still receive independent per-symbol tests, but must not be allowed to silently shorten the common-period portfolio test for the primary/reserve groups.

## Screening evidence
The existing H1 signal-quality ablation was screened across 50 symbols, 12 volume/breakout configurations, and three chronological folds. The consensus score combines median net PnL, fraction of positive symbol/configuration/fold runs, median profit factor, drawdown, and repeatability across folds. The primary/reserve split is a candidate allocation, not a statement that all five primary symbols are profitable. CAKEUSDT is retained as a primary growth candidate despite fold sensitivity; that sensitivity is precisely what the portfolio test must expose.

## Methodological caveats
- The existing source is a Binance OHLCV proxy, not actual Bybit candle/fill validation.
- Each symbol's earlier ablations used independent simulated capital. Their PnLs are not a shared-capital portfolio curve.
- Limit fills are OHLC penetration proxies; no order-book queue, partial fills, adverse selection, or actual spread model.
- The same historical archive has already been viewed during screening. Re-running the chosen universe is focused validation, **not an untouched blind test**.
- No production strategy or live symbol list is changed by this research shortlist.
