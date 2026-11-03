# ENG-DATA-001 — public Bybit instrument snapshot collector hardening

Статус: ACCEPT — collector code and mocked tests passed; live instrument snapshot remains BLOCKED by API HTTP 403.  
Дата: 2026-11-02.  
Тип: public market metadata only; no credentials and no trading side effects.

## Изменения

Усилен `scripts/snapshot_bybit_instruments.py`:

- HTTPS only and explicit allowlist of official Bybit public API hosts, including the regional hosts configured in the snapshot workflow.
- Redirects are disabled through a dedicated urllib opener.
- `retCode` must be an actual integer zero; boolean `False` is rejected (Python would otherwise compare it equal to zero).
- Response root and `nextPageCursor` types are validated.
- Pagination has a 1,000-page safety cap and still rejects repeated cursors.
- HTTP/URL failures are reported without printing response bodies.

The instrument snapshot workflow no longer runs on every code push. It is manual-dispatch only, avoiding a network-dependent red job on each code change. No scheduled retry is currently configured in .github/workflows/bybit-instrument-snapshots.yml.

## Tests and CI

`tests/test_snapshot_bybit_instruments.py`: 13 deterministic tests passed, including:
- complete pagination and stable symbol ordering;
- identical/conflicting duplicate symbol handling;
- repeated cursor and page-cap failures;
- strict boolean retCode rejection;
- official host allowlist and non-Bybit host rejection;
- UTC snapshot provenance and atomic JSON round-trip.

Full Research engine checks: [Actions #41468327832](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41468327832), SUCCESS.

## Live API result and limitation

The public instrument snapshot workflow attempted the configured regional Bybit hosts. The run [#41468304134](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41468304134) failed because the request returned HTTP 403 Forbidden. No instrument snapshot file was created or committed.

This is a network/access limitation, not an empty instrument universe and not evidence that the endpoint returned no instruments. Do not synthesize or substitute instrument specs. The dated Bybit instrument snapshot gate remains OPEN; execution sizing cannot yet claim historical Bybit spec fidelity.

## Decision

ACCEPT applies only to the hardened collector implementation and deterministic mocked tests. Live metadata capture remains BLOCKED until a real public endpoint response is obtained and archived with its timestamp and provenance. No PnL sweep, live order, production deployment or strategy change is authorized by this card.
