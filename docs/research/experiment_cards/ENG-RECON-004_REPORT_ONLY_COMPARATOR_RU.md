# ENG-RECON-004 — fail-closed report-only reconciliation comparator

Статус: ACCEPT — code and mocked CI tests passed; no live exchange reconciliation.  
Дата: 2026-11-02.  
Тип: local JSON comparison only; no network calls and no account/order mutation.

## Реализация

Добавлен `scripts/bybit_reconciliation_report.py`.

Входы:
- локальный `bot_state_backup.json`;
- сохранённый snapshot, созданный ENG-RECON-003.

Проверки:
- local backup envelope, UTC timestamp, position/pending object shape and trade sequence;
- snapshot schema version, linear/USDT scope, expected status and exact backup timestamp;
- SHA-256 of canonical raw exchange pages;
- strict parser validation for positions, active orders, historical orders and executions;
- counts vs validated rows/pages;
- historical-order interval coverage, statuses, order IDs and explicit Bybit retention limitations;
- server-time bounds and capture duration;
- contiguous execution interval coverage from backup time to snapshot boundary, each interval <= 7 days;
- local/exchange symbol coverage and direction conflicts;
- exchange-side position TP/SL/trailing-stop visibility, including missing or zero stop fields.

## Fail-closed decision

The comparator **never returns a reconciliation PASS**.

It always returns:
- `status = BLOCKED_UNSUPPORTED_LOCAL_MODEL`;
- `reconciliation_pass = false`;
- `live_resume_allowed = false`.

Причина: local `OpenPositionState` lacks exact exchange contract quantity and `positionIdx`; local backup lacks exchange `orderId/orderLinkId` mappings and a complete execution ledger. Local `pending_orders` are next-bar signal intents, not proof of exchange orders. Even if both sides show zero positions/orders/executions, the absence of a local execution ledger prevents a safe resume verdict.

The report surfaces counts, exchange identifiers, symbol mismatches and direction conflicts without pretending to establish exact position equality.

## Tests and CI

`tests/test_bybit_reconciliation_report.py`: 17 deterministic tests passed, covering:
- empty account still blocked;
- open position diagnostics without quantity reconciliation;
- direction conflict reporting;
- active exchange orders not matched to local pending signals;
- executions blocked without local ledger;
- raw SHA-256 tampering;
- backup timestamp mismatch;
- boolean count rejection;
- execution interval gaps;
- server-time chronology;
- non-object snapshot rejection;
- wrong market scope rejection.

CI: [Research engine checks #41468736376](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41468736376), SUCCESS. Comparator now rejects conflicting duplicate `execId` records across adjacent intervals rather than silently overwriting them. Latest full suite #41468736376 includes parser 16/16, collector 15/15, comparator 17/17 and instrument snapshot collector tests.

## Ограничения

- No real Bybit snapshot was fetched or compared.
- Historical order history is collected but remains partial under Bybit retention rules and may be delayed; no complete event journal or conditional-order health verification. Position-level TP/SL fields are reported when present, but do not prove trigger execution.
- No local execution ledger or exact exchange qty/positionIdx/order IDs.
- This is a diagnostic report, not permission to resume live trading.
- No PnL sweep, live order, production deployment or automatic recovery.
