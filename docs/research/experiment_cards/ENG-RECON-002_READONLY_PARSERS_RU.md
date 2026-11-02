# ENG-RECON-002 — strict read-only Bybit V5 snapshot parsers

Статус: ACCEPT — parser fixtures and CI passed.  
Дата: 2026-11-02.  
Тип: pure parsing/validation; no network or trading side effects.

## Реализация

Added `bybit_reconciliation.py` with strict parsers for caller-supplied, fully paginated Bybit V5 responses:
- linear positions, including one-way/hedge `positionIdx`;
- active orders with `qty`, `leavesQty`, `cumExecQty`;
- executions, including multiple fills per order and funding records;
- response `retCode`, row types, decimal finiteness, identifiers, timestamps, duplicate identities and cursor continuity/completion.

No HTTP client, credentials, private API call, order mutation or engine restore integration is present.

## Tests

`tests/test_bybit_reconciliation.py`: 12/12:
- complete multi-page positions and hedge-side identities;
- empty zero-size position rows;
- duplicate position/order/execution identities;
- incomplete/discontinuous pagination;
- Bybit error response not treated as empty account;
- partial fill quantity accounting;
- multiple executions per order;
- funding execution without trade side/price;
- malformed trade execution rejected.

## CI

- Parser commit: `fa97a4810e14d5d7590c5c4794ba2f98856127da`.
- Workflow/test integration commits: `95e5afb46a2869957e90742560f95d21089ddad5`, `b6d2fe255e692fa001fef5cf86274863485ae26d`.
- [Research engine checks #41448536690](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41448536690): SUCCESS; parser tests 12/12, persistence tests 54/54, compile, configured deterministic suites and secret scan passed.

## Ограничения

- Parser accepts already captured pages; it does not fetch them or prove that the caller queried every page from Bybit. Cursor-chain validation catches incomplete supplied captures.
- No snapshot freshness/server-time coherence check yet.
- No local-vs-exchange comparator yet.
- Current local position model still lacks exact contract qty, positionIdx and exchange order/execution IDs. Overall reconciliation remains `UNSUPPORTED_LOCAL_MODEL / BLOCKED`.
- No market PnL sweep, production deployment or live order.
