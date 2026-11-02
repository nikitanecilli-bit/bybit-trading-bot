# ENG-RECON-003 — fail-closed read-only Bybit V5 snapshot collector

Статус: ACCEPT — implementation and mocked CI coverage passed; real exchange capture is NOT verified.  
Дата: 2026-11-02.  
Тип: read-only authenticated collection; no order or account mutation.

## Реализация

Added `scripts/bybit_reconciliation_snapshot.py`.

- The API key identity and `readOnly == 1` flag are checked through `GET /v5/user/query-api` before any account snapshot endpoint.
- Credential-bearing requests are restricted to an explicit allowlist of Bybit API hosts. HTTP redirects are disabled.
- Bybit server time is captured before and after the collection; backwards time or a collection window over 120 seconds fails closed.
- Positions and active orders are fetched through complete cursor pagination.
- Historical orders are collected through `/v5/order/history` in <=7-day windows, with cursor pagination and deduplication by orderId/latest updatedTime; coverage is explicitly marked incomplete under Bybit retention rules.
- Execution history is split into intervals no longer than seven days, each with an independent cursor chain; parsed executions are deduplicated by `execId`.
- Repeated cursors and more than 1,000 pages per endpoint are rejected.
- Raw responses, capture metadata and SHA-256 are stored. Snapshot writes use temporary file, fsync, atomic replace and POSIX directory fsync.
- The workflow runs only mocked tests; it does not read API secrets or call Bybit.

## Tests

Report-only comparator: 17 deterministic tests passed in the same CI run. It rejects malformed/tampered snapshots, incomplete order-history metadata, interval gaps and conflicting execution identities; it always returns `BLOCKED_UNSUPPORTED_LOCAL_MODEL` and `live_resume_allowed=false`.

`tests/test_bybit_reconciliation_snapshot.py`: 15 deterministic collector tests passed for:
- signature construction;
- seven-day execution interval limits;
- read-only verification before account calls;
- server-time capture and execution boundary metadata;
- non-read-only key rejection;
- boolean `retCode=False` rejection;
- API errors not treated as empty account;
- repeated cursor rejection;
- HTTPS and official-host allowlist enforced before credentials are sent; redirect refusal;
- future backup timestamp rejection.

CI: [Research engine checks #41470373006](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41470373006), SUCCESS. Compile, all configured deterministic suites, parser tests (16/16), collector tests (15/15), secret scan and persistence tests completed successfully. The host validation and redirect protection are enforced in the actual request path. Cross-interval execution IDs are now deduplicated only when the complete parsed records match; conflicting records fail closed.

## Commits

- Collector initial: `bc62ee0d2de849bd8742fa67ec13a8f3fd0c1338`.
- Workflow integration/fixes: `3d2b150b3f2a2cc7928a7bf8925fe6fe6ca9f501`, `6e06d3155bfc351c6e258127426bcda9150f9a58`.
- Server-time, atomic-write, host-security and pagination hardening: `49ea05fb32b73b4f3fde41d16b19bd04d5357a78`, `9e3770b9183efc5812e5c702c3a63f64d42c1a83`, `8a6b5efc0199b1b707d12ac95eeb508e900e53e7`, `4f6470ee0955de0beafba25d010f2266ba25dc5d`, `89853634a76814b537d869074b9cfccaae093630`, `033aa3e8d9da9b57de70af1f59369d9451e02a02`, `928a43782c5dc5dd91c94ea0034b3fdb448f953b`, `423e7fb3f15c5674aa8f99f44e2f448dbc52db03`, `1dd1a86dae9cea158c8e664a784dfb93cbaad4f2`.

## Ограничения и вердикт

- No live Bybit request was made and no real snapshot exists from this implementation. ACCEPT applies only to code and mocked CI coverage.
- Collector output status is `CAPTURED_READ_ONLY_NOT_RECONCILED`, never a reconciliation PASS.
- Order history and exchange-side stop/TP verification are not included.
- The local engine still lacks exact exchange qty, `positionIdx`, order identifiers and execution ledger; comparator must remain BLOCKED for open positions/orders.
- Order-history completeness is limited by Bybit's documented 24h/7d status retention rules and asynchronous updates. Prior GitHub-runner HTTP 403 remains unresolved. No PnL sweep, live order, production deployment or live resume.
- Audit correction: earlier revisions documented the host allowlist/redirect guard before they were wired into `collect_snapshot()` and `_http_json()`. This was caught by the failing host-allowlist test in run #41452045788, fixed in commit `455182c4d0db3f761f35562d542c9a57cad11797`, and re-verified with redirect regression coverage in #41457143134.
