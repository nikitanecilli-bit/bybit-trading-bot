# Bybit Announcement Inventory — Content Extraction Gap

**Date:** 2026-11-25  
**Workflow run:** [45586354775](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/45586354775)  
**Artifact:** `bybit-public-announcement-inventory`  
**Scope:** Independent QA of the downloaded artifact, not a new crawl.

## Finding

The inventory has 1,275 article records and 1,275 captured article HTML bodies, but **five articles have an empty `articleDetail.content_html` field** in the embedded `__NEXT_DATA__` payload. Their raw HTML pages are present and their byte hashes/sizes match the manifest; therefore this is a content-extraction gap, not a missing or corrupted download.

Corrected interpretation:
- 1,270/1,275 article payloads contain non-empty visible article text.
- 5/1,275 have no visible article text in `content_html`.
- All 1,275 have a publication timestamp.
- The collector currently labels all records with `content_extraction=next_data_articleDetail.content_html` even when the field is empty, and its `complete` condition checks page capture/failures but not non-empty article text. Therefore the workflow's `complete=true` is too permissive for semantic completeness.
- All five gaps are risk-limit announcement candidates. Their symbol matches are title-derived only and must not be used to establish the content, values, or effective terms of the risk change.

## Affected articles

| Published timestamp | Title | Title-matched proxy symbols | Raw body SHA-256 |
|---|---|---|---|
| 2026-06-29T11:53:30+08:00 | Risk limit adjustment for selected Perpetual Contracts HBARUSDT,ROSEUSDT...(Jun 30, 2026) | HBARUSDT | `60fb043647255f4dacca93eb1cabf0fe376c76097c9632572ea0d7984dbce55a` |
| 2026-01-21T22:06:30+08:00 | Risk limit adjustment for selected Perpetual Contracts ONTUSDT,QNTUSDT...(Jan 23, 2026) | QNTUSDT | `68cf36088690ac689f010377dea366e8c6dd3f987a5da6e687d9223d1fdacf73` |
| 2026-06-11T15:00:50+08:00 | Risk limit adjustment for selected Perpetual Contracts PAXGUSDT,GALAUSDT...(Jun 12, 2026) | PAXGUSDT | `464a8b90878e3b5df0a10805d4ed1fcb6e62d4e655c2eb1d969e9d7263780079` |
| 2026-04-27T19:12:10+08:00 | Risk limit adjustment for selected Perpetual Contracts POLUSDT,ALGOUSDT...(Apr 28, 2026) | ALGOUSDT, POLUSDT | `facbc01dceadfc70c7f63cbefb7dd4483f35ea357805105271cdbbc7f20397da` |
| 2026-04-01T20:20:10+08:00 | Risk limit adjustment for selected Perpetual Contracts XRPUSDT,XAGUSDT...(Apr 2, 2026) | XRPUSDT | `1e1cd8d11a9d55faf7f80a4b8cec8aff2c845f3a39eae0ea4fb0c2886a0aec61` |

The exact source pages are preserved in the artifact under the corresponding `articles/*.html` paths. The original article HTML itself does not contain a populated `content_html` value in its structured payload.

## Required correction

1. Change `extract_article_payload` to reject empty/whitespace-only `content_html` or content with no visible text.
2. Let the existing per-article exception path record these as extraction failures. Keep the raw HTML capture even when extraction fails.
3. Add a regression test for an empty `content_html` payload.
4. Define semantic completeness as: all category pages captured, every unique article HTML captured, every article payload parsed, and every article has non-empty visible content. A run with any empty article body must be `complete=false`.
5. Re-run the offline tests and bounded public crawl. Do not silently drop these five records or infer their contents from titles/current market API.
6. Keep D6 (dated risk-limit tiers) **NOT ACCEPTED** until these and other candidate articles are recovered and the actual tier values/effective times are independently checked.

## Gate impact

This finding does not invalidate the raw-byte integrity result or the 66 category-page / 1,275 article-page download counts. It narrows what can be claimed: the artifact is byte-complete against its manifest, but not semantically complete for article content. The five affected candidate articles cannot support D6 evidence in their current form.
