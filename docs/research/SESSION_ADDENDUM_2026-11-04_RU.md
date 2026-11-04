# Session addendum — 2026-11-04

Рабочая ветка: `research/market-regime-v1-main`.

## Последние подтверждённые изменения

- [ENG-EXEC-041](ENG_EXEC_041_NONPOSITIVE_TRADE_TIMESTAMP_RU.md): normalized public trade timestamp must be positive. Code/test commit `ed2d355`; Research CI #41891208250 SUCCESS.
- [ENG-EXEC-042](ENG_EXEC_042_EXPLICIT_INSTRUMENT_CATEGORY_RU.md): explicit instrument category required; missing/blank/non-string category no longer defaults to `linear`. Code/test commit `b1fafc3b69fe71cb5d97408689b2ee7403f8191f`; Research CI #41892075429 SUCCESS.

## ENG-EXEC-042 verification

- `tests/test_bybit_instrument_specs.py`: 14/14.
- `tests/test_instrument_spec_history.py`: 12/12.
- `tests/test_exchange_order_sizing.py`: 10/10.
- Compile, snapshot collector tests and portfolio exchange-sizing integration CI steps: SUCCESS.

## Current gates and restrictions

- Maker execution realism remains BLOCKED; the L2 aggregate queue replay is engineering evidence only, not strategy PnL or an execution-rate estimate.
- No verified dated Bybit instrument snapshot, risk-tier snapshot or account-specific fee schedule is claimed.
- Do not run market/PnL tests, collectors, archive downloads, private/account API or live/paper orders until the corresponding user-controlled gates are explicitly opened.
- Do not modify `main`; do not merge PR #4.

## Next safe work

Continue static audit of report/input provenance and exchange-spec validation. Prefer deterministic tests for demonstrated contract gaps. Do not rerun already-passing suites without a new reason.


## Дополнение — symbol parsing

- Commit `2c00abd10803030e6e4cc1536339afdbad544d05`: `InstrumentSpec.from_snapshot()` теперь требует явный непустой строковый `symbol`, не принимает numeric/boolean coercion.
- Regression tests: instrument spec suite **15/15**.
- Research CI [#41892392949](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41892392949): SUCCESS; job `tests` SUCCESS.


## Дополнение — instrument snapshot input contract

- Оба сборщика теперь отклоняют отсутствующий, пустой или нестроковый `symbol`; тесты покрывают numeric/boolean/whitespace значения.
- Проверена официальная схема Bybit: category находится в `result.category`, а не обязательно в каждой записи `result.list`. As-of history loader теперь берёт category из проверенного snapshot envelope только при отсутствии row-level значения; противоречивое row-level значение остаётся ошибкой.
- Изменения кода: `8c04cde`, `ff7e5bb`, `c069075`; тесты: `f7ef140`, `c9096a7`, `3025039`.
- Полный Research CI для head `302503937f47277ab0ee7a83c2a0247bcf51a81c`: все функциональные шаги включая instrument parser, два snapshot collectors, as-of history и sizing прошли SUCCESS; финальный статус workflow ожидает завершения post-job cleanup на момент записи.
- CI выполняет зафиксированные offline/research проверки и аудит уже имеющихся CryptoFetch архивов; новые архивы не загружались, Bybit collectors вручную не запускались, market PnL/live/private API не запускались.
