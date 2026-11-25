# Bybit Listing/Delisting Lifecycle Scan — 47-Symbol Proxy (Partial)

**Review date:** 2026-11-25  
**Source artifact:** workflow [45586354775](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45586354775), artifact `bybit-public-announcement-inventory`  
**Scope:** 66 category pages across `new_crypto`, `delistings`, `maintenance_updates`, `latest_bybit_news`; 1,275 captured article pages. Body text was independently extracted from either `content_html` or Contentstack rich-text `content.json`.

## Result

A bounded scan searched article titles and body text for listing/delisting lifecycle language and exact or separator-normalized references to the frozen 47-symbol proxy universe.

**Result: 0 confirmed listing/delisting candidate articles matched any of the 47 proxy symbols.**

This is a negative search result for this specific proxy and selected archive capture. It is not evidence that the symbols were never listed or delisted by Bybit.

## Why this does not accept D4

- The 47-symbol set is a Binance-style survivor-biased proxy, not a Bybit point-in-time instrument universe.
- The capture covers four announcement categories and the pagination exposed on 2026-11-25; it is not proof of complete historical announcement coverage.
- Listing/delisting notices may refer to other product types (Spot, Alpha, TradFi, Options, Convert) and cannot be treated as linear USDT perpetual lifecycle events without product-specific evidence.
- A zero match for this proxy does not establish zero lifecycle events for Bybit or for the actual historical linear universe.

## Decision

**D4 — NOT ACCEPTED.** The current proxy does not produce usable listing/delisting coverage from the captured archive. The next valid route is to establish a Bybit-specific point-in-time universe first, then link each instrument's exact product category, listing time, trading status transitions and delisting time to official notices or dated instrument snapshots.

No market API, private/account API, orders, PnL or backtests were used for this scan.
