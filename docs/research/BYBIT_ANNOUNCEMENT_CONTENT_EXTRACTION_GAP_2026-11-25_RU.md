# Bybit Announcement Content QA — Correction and Resolution

**Review date:** 2026-11-25  
**Source workflow:** [45586354775](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45586354775)  
**Artifact:** `bybit-public-announcement-inventory` (1,275 article pages; artifact SHA-256 `2145c610aa4a5b963981fc7eee08f6f218ae4d067e80327cc40ed59ea6b694fe`)

## Correction to the earlier five-article finding

The earlier version of this report incorrectly treated an empty `articleDetail.content_html` field as proof that an article had no body. That conclusion was wrong.

Bybit stores article content in two formats:
1. rendered HTML in `articleDetail.content_html`;
2. Contentstack rich-text JSON in `articleDetail.content.json`.

Independent inspection of all 1,275 captured article payloads found:

| Content source | Articles |
|---|---:|
| Non-empty `content_html` | 721 |
| Empty `content_html`, non-empty `content.json` | 554 |
| Empty in both formats | 0 |
| **Total with visible article text** | **1,275 / 1,275** |

The five risk-limit articles listed in the previous version all contain their full body text in `content.json`; their raw-body SHA-256 values remain valid. They are not missing articles and must not be reported as content-extraction failures.

The earlier claim that five pages had no visible text, and the proposed treatment of those five as unresolved gaps, is superseded by this correction.

## Corrective implementation

The collector now:
- prefers `content_html` when it contains visible text;
- falls back to recursively extracting ordered text nodes from `content.json`;
- records which source was used and the extracted text length;
- ignores script/style text when parsing HTML;
- includes non-empty article text in the collector's own `complete` condition.

The semantic validator uses the same extractor. It continues to fail closed for a genuinely empty article, missing body, unsafe path, parse failure, or raw-byte hash/size mismatch.

Regression tests cover HTML extraction, rich-text JSON fallback, truly empty content, and raw-byte hash mismatch.

## What this does and does not prove

- The existing artifact has 1,275/1,275 article pages captured and byte-integrity metadata in its manifest.
- The independent content-format audit found visible text for all 1,275 pages using the two supported payload fields. Extracted body lengths ranged from 199 to 20,000+ characters; median length was 1,069 characters and the 10th percentile was 692 characters. No article had fewer than 120 extracted characters.
- This is not a new crawl. The corrected extractor still needs to be exercised by the next manual full-archive run.
- Archive-page pagination counts are the observed 2026-11-25 baseline, not proof that Bybit exposes every historical announcement.
- The 47-symbol set remains a proxy universe, not a verified historical Bybit universe.

## Gate impact

The five-page extraction-gap finding is **RESOLVED / WITHDRAWN**. This correction does not change the separate research gates:
- **D4 — NOT ACCEPTED:** historical listing/delisting lifecycle is not yet complete.
- **D5 — NOT ACCEPTED:** dated instrument parameter history remains partial.
- **D6 — NOT ACCEPTED:** risk-limit notices provide dated change events and affected-symbol evidence, but not a complete historical tier ladder with notional thresholds and maintenance-margin rates.
