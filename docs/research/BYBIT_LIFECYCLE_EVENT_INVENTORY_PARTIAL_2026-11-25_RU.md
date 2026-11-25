# Bybit Listing/Delisting Lifecycle — Partial 2026 Event Inventory

**Review date:** 2026-11-25  
**Source artifact:** workflow [45586354775](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45586354775), artifact `bybit-public-announcement-inventory`  
**Scope:** 66 category pages and 1,275 captured article pages from `new_crypto`, `delistings`, `maintenance_updates`, `latest_bybit_news`. Body text was read from `content_html` or Contentstack rich-text `content.json`.

## 1. Lifecycle evidence found

The captured archive contains the following title-level event candidates:

| Event group | Announcement articles | Distinct symbols | Time evidence |
|---|---:|---:|---|
| New USDT perpetual listing candidates | 238 | 236 | 301/304 total listing articles say “Trading is now open”; publication timestamp confirms availability by then, but is not the exact listing start |
| New TradFi perpetual listings | 62 | Not treated as crypto universe | Product class stated in title |
| New Pre-IPO perpetual listings | 3 | One article contains two symbols | Product class stated in title |
| New inverse perpetual listings | 1 | 1 | Separate product class |
| USDT perpetual delistings | 106 | 106 | All 106 have explicit UTC delisting times in article bodies |
| USDC perpetual delistings | 1 | 1 | Explicit UTC delisting time |
| Inverse perpetual delistings | 1 | 1 | Explicit UTC delisting time |

There are 304 listing announcement articles, including one Pre-IPO article naming two symbols. Two linear listing symbols (KORUUSDT and SPCXUSDT) appear in more than one listing notice, so 238 linear listing notices correspond to 236 distinct symbols.

These are announcement candidates, not an accepted point-in-time universe. The `Perpetual` title class can include equity/index underlyings; a crypto-only strategy still needs an underlying-asset/product filter. TradFi, Pre-IPO, inverse and USDC contracts must not be silently mixed into a USDT linear crypto universe.

## 2. Verified examples outside the 47-symbol proxy

The following official notices demonstrate that the captured Bybit universe contains instruments absent from the 47-symbol proxy:

| Symbol | Event | Published | Effective / availability evidence | Official source |
|---|---|---|---|---|
| TMXUSDT | Listing | 2026-08-26 10:47:45Z | Body says trading is now open; exact start time not stated | [Listing notice](https://announcements.bybit.com/en/article/new-listing-tmxusdt-perpetual-contract-in-innovation-zone-with-up-to-20x-leverage--art67882b7f60b4/) |
| TMXUSDT | Delisting | 2026-10-28 09:04:42Z | 2026-10-30 09:00 UTC | [Delisting notice](https://announcements.bybit.com/en/article/delisting-of-tmxusdt-perpetual-contract--art1017f3d4607b/) |
| AGIUSDT | Delisting | 2026-11-11 08:59:10Z | 2026-11-13 09:00 UTC | [Delisting notice](https://announcements.bybit.com/en/article/delisting-of-agiusdt-perpetual-contract--art7816e6629a54/) |
| ASPUSDT | Delisting | 2026-09-03 09:00:34Z | 2026-09-05 09:00 UTC | [Delisting notice](https://announcements.bybit.com/en/article/delisting-of-aspusdt-perpetual-contract--artd07ca3b584f4/) |
| IPUSDT | Delisting | 2026-06-23 14:59:30+08:00 | 2026-06-26 07:00 UTC | [Delisting notice](https://announcements.bybit.com/en/article/delisting-of-ipusdt-perpetual-contract-blt6ded6acc1447f3ec/) |

The bounded scan found zero listing/delisting candidate articles matching the 47-symbol proxy. The positive lifecycle notices above are outside that proxy, which confirms the proxy is not a suitable Bybit universe source.

## 3. Extraction semantics

The new offline extractor `scripts/extract_bybit_lifecycle_events.py` creates per-symbol candidate events and preserves:
- publication timestamp in its source timezone and normalized UTC;
- explicit delisting effective time when stated in the article body;
- listing availability confirmation at publication only when the body says “Trading is now open”;
- `effective_at_utc = null` when the exact listing start is not stated;
- product-class candidate, underlying-asset candidate, article URL, raw body path, byte count and SHA-256;
- whether the symbol intersects the 47-symbol proxy.

Publication time is never silently relabeled as the exact listing effective time. Raw source bytes must match the manifest before an event is emitted.

## 4. Why D4 is still not accepted

- No verified Bybit point-in-time starting universe exists for the beginning of the research period. Listing notices from 2026 cannot tell us which contracts were already active on 2026-01-01.
- Listing notices often say “Trading is now open” but do not state the exact first-trade timestamp. Publication time is a conservative availability confirmation, not the exact event time.
- Product classification needs review, especially equity/index underlyings within generic USDT perpetual titles.
- The four-category archive and observed pagination counts are not proof of exhaustive historical coverage.
- Additional instrument status changes and symbol transformations may be recorded in maintenance notices rather than listing/delisting titles.

## 5. Decision

**D4 — PARTIAL EVIDENCE / NOT ACCEPTED.** The capture provides strong dated delisting evidence and a substantial set of listing candidates, but not a complete Bybit-specific point-in-time universe. The 47-symbol proxy is rejected as a substitute for that universe.

Next step: run the new offline lifecycle extractor against the corrected full-crawl artifact, manually review ambiguous product classes and date fields, then combine the event stream with dated Bybit instrument snapshots. Do not start historical performance tests until the D4 universe gate is accepted.
