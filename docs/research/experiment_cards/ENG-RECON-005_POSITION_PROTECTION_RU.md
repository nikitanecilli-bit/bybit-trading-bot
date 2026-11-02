# ENG-RECON-005 — exchange-side position protection visibility

Статус: ACCEPT — parser/report code and mocked CI coverage passed; no live position snapshot.  
Дата: 2026-11-02.  
Тип: read-only field preservation and diagnostic reporting.

## Изменение

Bybit V5 `GET /v5/position/list` documents position fields `takeProfit`, `stopLoss`, `trailingStop` and `tpslMode` ([official API documentation](https://bybit-exchange.github.io/docs/v5/position)).

`PositionSnapshot` now preserves these fields as Decimal/optional values. The report-only comparator includes them in its exchange position rows and classifies protection visibility:
- `EXCHANGE_STOP_CONFIGURED`: non-zero stopLoss or trailingStop;
- `NO_EXCHANGE_STOP`: both stopLoss and trailingStop are zero;
- `UNKNOWN_FIELDS_MISSING`: response did not include the required stop fields.

This reports configuration visible in the position response only. It does not prove trigger execution, exchange-side order health, or equivalence with local strategy stop logic.

## Tests and CI

- Parser tests: 16/16.
- Comparator tests: 17/17.
- Collector tests: 15/15.
- Full workflow: [Research engine checks #41468327832](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41468327832), SUCCESS.
- Coverage includes valid TP/SL parsing, negative stop-price rejection, configured stop, missing stop and unknown fields.

## Ограничения

- No live Bybit API call or real position snapshot was made.
- Position-level TP/SL fields do not replace reading active/conditional order details or order history.
- Local model still lacks exact exchange qty, positionIdx, exchange order IDs and a complete execution ledger.
- Overall reconciliation and live resume remain BLOCKED. No PnL sweep or trading mutation.
