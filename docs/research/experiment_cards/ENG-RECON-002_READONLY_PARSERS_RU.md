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

`tests/test_bybit_reconciliation.py`: 16/16:
- complete multi-page positions and hedge-side identities;
- empty zero-size position rows;
- duplicate position/order/execution identities;
- incomplete/discontinuous pagination;
- Bybit error response and boolean `retCode=False` are not treated as integer success or empty account;
- partial fill quantity accounting;
- multiple executions per order;
- funding execution without trade side/price;
- malformed trade execution rejected.

## CI

- Parser commits: `fa97a4810e14d5d7590c5c4794ba2f98856127da`, `b035edbff03a11299b74c3e44eea4fcb027c5bd8`.
- Workflow/test integration commits: `95e5afb46a2869957e90742560f95d21089ddad5`, `9fdaa02d764495a59747f0930e89fa677d03b890`.
- Initial parser CI: #41448536690 passed (12/12). Subsequent parser hardening added strict cross-interval execution deduplication and a 1,000-page cap. Latest parser CI: [#41468736376](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41468736376), SUCCESS; 16/16 parser tests and full configured workflow passed.

## Ограничения

- Parser accepts already captured pages; it does not fetch them or prove that the caller queried every page from Bybit. Cursor-chain validation catches incomplete supplied captures.
- No snapshot freshness/server-time coherence check yet.
- No local-vs-exchange comparator yet.
- Current local position model still lacks exact contract qty, positionIdx and exchange order/execution IDs. Overall reconciliation remains `UNSUPPORTED_LOCAL_MODEL / BLOCKED`.
- No market PnL sweep, production deployment or live order.


## Follow-up: position protection fields

The parser now also preserves optional Bybit position `takeProfit`, `stopLoss`, `trailingStop` and `tpslMode` fields. See [ENG-RECON-005](ENG-RECON-005_POSITION_PROTECTION_RU.md). Parser coverage is now 14/14; full workflow #41459486381 passed.
