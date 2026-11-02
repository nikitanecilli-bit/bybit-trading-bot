# ENG-RECON-006 — paginated historical order capture with explicit retention limits

Статус: ACCEPT — code and mocked CI coverage passed; no live exchange capture.  
Дата: 2026-11-02.  
Тип: authenticated read-only order-history collection and report-only diagnostics.

## Реализация

`scripts/bybit_reconciliation_snapshot.py` теперь дополнительно вызывает `GET /v5/order/history`:
- `category=linear`, `settleCoin=USDT`;
- time windows are split into <=7-day intervals;
- each interval has its own cursor pagination;
- historical rows are parsed using strict order quantity/identity validation;
- duplicates across adjacent windows are deduplicated by `orderId`, keeping the newest `updatedTime`; conflicting records with the same update timestamp fail closed;
- raw pages and interval boundaries are included in the canonical SHA-256 snapshot.

Coverage metadata is explicit:
`order_history_coverage.status = QUERYABLE_WINDOW_ONLY_NOT_COMPLETE`.

## Bybit API limitation (must not be hidden)

Official [Get Order History](https://bybit-exchange.github.io/docs/v5/order/order-list) rules:
- `startTime` to `endTime` max span is 7 days per request;
- within the last 7 days, closed statuses are queryable except `Cancelled`, `Rejected`, `Deactivated`;
- those statuses are queryable only within the last 24 hours;
- beyond 7 days, only orders with fills are queryable;
- Bybit notes that order creation/cancellation data may be delayed.

Therefore this endpoint is a useful supplement, **not a complete order-event journal for arbitrary outage periods**. The comparator validates and displays this limitation and never upgrades it to a complete state.

## Comparator and tests

`scripts/bybit_reconciliation_report.py` validates:
- presence and matching coverage windows for historical-order pages and execution pages;
- strict parsing, counts and interval continuity;
- historical order IDs/statuses and API coverage metadata;
- no reconciliation PASS is ever possible. Exact duplicate executions at interval boundaries are deduplicated; conflicting records sharing an `execId` block the report.

CI: [Research engine checks #41468736376](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41468736376), SUCCESS:
- parser 16/16;
- collector 15/15;
- comparator 17/17;
- persistence 54/54;
- configured deterministic suites and secret scan passed.

## Ограничения

- No real Bybit API request or real account snapshot was made.
- Order history remains partial under Bybit's documented retention/status rules.
- No full local execution ledger, exact exchange qty, positionIdx, order identity map or conditional-order event history.
- Comparator always returns `BLOCKED_UNSUPPORTED_LOCAL_MODEL`; live resume, PnL sweeps and trading mutations remain blocked.
