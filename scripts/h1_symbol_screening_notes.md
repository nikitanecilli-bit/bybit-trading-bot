# H1 symbol shortlist — research only

## Primary candidates (5)
1. LINKUSDT
2. RAYUSDT
3. PUMPUSDT
4. APTUSDT
5. TAOUSDT

## Reserve candidates (5)
1. POLUSDT
2. AAVEUSDT
3. CAKEUSDT
4. DOGEUSDT
5. ATOMUSDT

## Why these ten
Screened the existing H1 signal-quality ablation across 50 symbols, 12 volume/breakout configurations, and three chronological folds. The shortlist uses a consensus score across median net PnL, fraction of positive symbol/configuration/fold runs, median profit factor, drawdown, and repeatability across folds. The ranking is not just the sum of PnL across 50 instruments.

The primary/reserve split is a **candidate allocation**, not a statement that all five primary symbols are profitable. Some candidates have low trade counts or regime sensitivity; the next runs must show results per symbol and by fold. CAKEUSDT is retained as a reserve growth candidate despite instability across folds.

## Methodological caveats
- The existing source is a Binance OHLCV proxy, not actual Bybit candle/fill validation.
- Each symbol's earlier ablations used independent simulated capital. Their PnLs are not a shared-capital portfolio curve.
- Limit fills are OHLC penetration proxies; no order-book queue, partial fills, adverse selection, or actual spread model.
- The same historical archive has already been viewed during screening. Re-running the chosen universe is useful focused analysis but is **not an untouched blind test**.
- No production strategy or live symbol list is changed by this research shortlist.
