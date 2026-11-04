# ENG-EXEC-042 — explicit Bybit instrument category validation

Дата: 2026-11-04

## Найденный риск

`InstrumentSpec.from_snapshot()` ранее вычислял category через `str(instrument.get("category") or "linear")`. Отсутствующее, пустое или иное false-like значение автоматически классифицировалось как `linear`.

Это fail-open поведение: неполная/повреждённая запись могла пройти проверку категории как linear contract. Остальные обязательные поля могли быть корректны, поэтому последующая проверка category сама по себе не выявляла отсутствие исходного поля.

## Исправление

- Требовать явное непустое строковое поле `category`.
- Нормализовать регистр только после проверки типа и непустого значения.
- Сохранять прежний отказ для категорий, отличных от `linear`.
- Добавить регрессионный тест для отсутствующего поля, `None`, пустой строки, строки из пробелов и числового значения.

Файлы:
- `bybit_instrument_specs.py`
- `tests/test_bybit_instrument_specs.py`

## Проверка

- Commit: [b1fafc3](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/b1fafc3b69fe71cb5d97408689b2ee7403f8191f).
- Research CI: [#41892075429](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41892075429) — SUCCESS; job `tests` SUCCESS.
- Фактические логи: `test_missing_or_malformed_category_fails_closed` — PASS; `tests/test_bybit_instrument_specs.py` — 14/14; `tests/test_instrument_spec_history.py` — 12/12; `tests/test_exchange_order_sizing.py` — 10/10.
- CI также подтвердил compile step, snapshot collector tests и portfolio exchange-sizing integration step.

## Границы

Изменение влияет только на parsing/validation входной спецификации. Торговая логика, sizing arithmetic, комиссии и исторические результаты не изменялись. Никакие Bybit API, collectors, archive downloads, market/PnL replay, private API или orders не запускались. `main` не изменён. Реальные исторические Bybit snapshots по-прежнему отсутствуют; исправление не открывает data/execution/PnL gates.


## Дополнительная проверка символа

Смежное поле `symbol` также ранее проходило через `str(...)`, поэтому числовое/boolean значение могло превращаться в строковый псевдо-символ. Исправлено в отдельном code/test commit [2c00abd](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/2c00abd10803030e6e4cc1536339afdbad544d05): теперь требуется явное непустое строковое поле symbol; отсутствующие, пустые, числовые и boolean значения отклоняются.

- Research CI [#41892392949](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41892392949): SUCCESS; job `tests` SUCCESS.
- Фактический лог `tests/test_bybit_instrument_specs.py`: **15/15 passed**, включая новые regressions для category и symbol.
- Остальные затронутые CI steps (compile, snapshot collector, as-of history, exchange sizing integration) завершились SUCCESS.
- Никакие внешние API, collectors или market data downloads не запускались этой задачей; CI выполнял только уже определённые repo checks.
