# Bybit Listing/Delisting Lifecycle — Partial 2026 Event Inventory

**Review date:** 2026-11-25  
**Latest full-crawl artifact:** workflow [45603180553](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45603180553), artifact ID `15019447571`, `bybit-public-announcement-inventory`.  
**Artifact SHA-256:** `97269198002e7292d4ff3117cfa14ec78ad8f36abb2370d76c5c1a5aade17350`.  
**Scope:** 66 category pages (25 `new_crypto`, 11 `delistings`, 19 `maintenance_updates`, 11 `latest_bybit_news`) and 1,280 unique captured article pages. All 1,280 article bodies were non-empty and passed raw-body integrity and semantic-content validation; zero collection or content-validation failures.

This supersedes the earlier 1,275-article snapshot referenced by workflow 45586354775. The later offline Research CI [45603306746](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45603306746) passed the updated parser/safety tests and the fail-closed incomplete-inventory extraction guard. Its full-crawl steps were correctly skipped because it was a normal push, not a full-archive dispatch. The existing 45603180553 archive itself records `complete=true` and `content_validation.semantic_complete=true`, satisfying the newer extractor's input gate.

## 1. Lifecycle evidence found

The offline extractor produced 497 per-symbol event rows across 488 distinct symbols: 386 listing rows and 111 delisting rows. These are event candidates, not an accepted point-in-time universe.

| Event group | Announcement articles | Distinct symbols | Time evidence |
|---|---:|---:|---|
| Linear USDT perpetual listing candidates | 241 | 240 | All 241 article rows say trading is open by publication; exact first-trade time is not stated |
| TradFi perpetual listing candidates | 138 | 138 | Kept separate from crypto universe |
| Pre-IPO perpetual listing candidates | 3 | 4 | One article names two symbols; not treated as ordinary crypto listings |
| Inverse perpetual listing candidates | 1 | 1 | Separate product class |
| Unknown-class listing candidates | 2 | 2 | Manual product review required |
| Linear USDT perpetual delistings | 106 | 106 | All 106 have explicit UTC effective times |
| USDC perpetual delisting | 1 | 1 | Explicit UTC effective time |
| Inverse perpetual delisting | 1 | 1 | Explicit UTC effective time |
| Pre-IPO perpetual delisting | 1 | 1 | No accepted crypto-universe interpretation |
| Unknown-class delistings | 2 | 2 | Manual product review required |

There are 385 distinct listing article URLs but 386 listing symbol rows because one notice names multiple symbols. Across the complete event output, 304 listing rows confirm that trading was already open at publication; this is an availability upper-bound observation, not an exact listing start. Of 111 delisting rows, 110 have an explicit effective UTC timestamp.

The extractor reported zero event-extraction failures, 65 out-of-scope article records, and `scope_review_required=true`. No event row matched the prior 47-symbol proxy. The 488-symbol count spans multiple product classes and must not be interpreted as 488 eligible crypto USDT perpetual contracts.

These are announcement candidates, not an accepted point-in-time universe. The `Perpetual` title class can include equity/index underlyings; a crypto-only strategy still needs an underlying-asset/product filter. TradFi, Pre-IPO, inverse, USDC and unknown-class contracts must not be silently mixed into a USDT linear crypto universe.

## 2. Verified examples outside the 47-symbol proxy

The following official notices demonstrate that the captured Bybit universe contains instruments absent from the 47-symbol proxy:

| Symbol | Event | Published | Effective / availability evidence | Official source |
|---|---|---|---|---|
| TMXUSDT | Listing | 2026-08-26 10:47:45Z | Body says trading is now open; exact start time not stated | [Listing notice](https://announcements.bybit.com/en/article/new-listing-tmxusdt-perpetual-contract-in-innovation-zone-with-up-to-20x-leverage--art67882b7f60b4/) |
| TMXUSDT | Delisting | 2026-10-28 09:04:42Z | 2026-10-30 09:00 UTC | [Delisting notice](https://announcements.bybit.com/en/article/delisting-of-tmxusdt-perpetual-contract--art1017f3d4607b/) |
| AGIUSDT | Delisting | 2026-11-11 08:59:10Z | 2026-11-13 09:00 UTC | [Delisting notice](https://announcements.bybit.com/en/article/delisting-of-agiusdt-perpetual-contract--art7816e6629a54/) |
| ASPUSDT | Delisting | 2026-09-03 09:00:34Z | 2026-09-05 09:00 UTC | [Delisting notice](https://announcements.bybit.com/en/article/delisting-of-aspusdt-perpetual-contract--artd07ca3b584f4/) |
| IPUSDT | Delisting | 2026-06-23 14:59:30+08:00 | 2026-06-26 07:00 UTC | [Delisting notice](https://announcements.bybit.com/en/article/delisting-of-ipusdt-perpetual-contract-blt6ded6acc1447f3ec/) |

The scan found zero listing/delisting event rows matching the 47-symbol proxy. The positive lifecycle notices above are outside that proxy, which confirms the proxy is not a suitable Bybit universe source.

## 3. Extraction semantics and integrity

The offline extractor `scripts/extract_bybit_lifecycle_events.py` creates per-symbol candidate events and preserves:
- publication timestamp in its source timezone and normalized UTC;
- explicit delisting effective time when stated in the article body;
- listing availability confirmation at publication only when the body says “Trading is now open”;
- `effective_at_utc = null` when the exact listing start is not stated;
- product-class candidate, underlying-asset candidate, article URL, raw body path, byte count and SHA-256;
- whether the symbol intersects the 47-symbol proxy.

The collector is restricted to public HTTPS pages on `announcements.bybit.com`; it does not call market/account APIs or use credentials. The content validator checks every article body against its recorded byte count and SHA-256 and rejects empty/unparseable content. The extractor now fails closed unless the inventory is complete and semantic content validation passed.

Publication time is never silently relabeled as the exact listing effective time. Raw source bytes must match the inventory manifest before an event is emitted.

## 4. Why D4 is still not accepted

- No verified Bybit point-in-time starting universe exists for the beginning of the research period. Listing notices from 2026 cannot tell us which contracts were already active on 2026-01-01.
- Listing notices often say “Trading is now open” but do not state the exact first-trade timestamp. Publication time is a conservative availability confirmation, not the exact event time.
- Product classification needs review, especially equity/index underlyings within generic USDT perpetual titles; 65 out-of-scope records and two unknown-class listing plus two unknown-class delisting candidates require classification decisions.
- The four-category archive and observed pagination counts are not proof of exhaustive historical coverage, even though all pages observed in this crawl were captured.
- Additional instrument status changes and symbol transformations may be recorded in maintenance notices rather than listing/delisting titles.
- Dated instrument snapshots are still required to establish status/eligibility between announcement events and to anchor contracts already active before the captured listing history.

## 5. Decision

**D4 — PARTIAL EVIDENCE / NOT ACCEPTED.** The 1,280-article capture provides substantial dated delisting evidence and listing candidates, but not a complete Bybit-specific point-in-time universe. The 47-symbol proxy remains rejected as a substitute for that universe.

Next step: manually review ambiguous product classes and event-time fields, then reconcile the event stream with already available dated Bybit instrument snapshots. Do not start historical performance tests until the D4 universe gate is accepted. No new market-PnL tests or market-data collection are authorized by this report.
