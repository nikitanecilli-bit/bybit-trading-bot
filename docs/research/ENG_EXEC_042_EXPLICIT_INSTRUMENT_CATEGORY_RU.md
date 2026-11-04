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


## Дополнительная проверка формата публичного API и снимков

Официальная схема Bybit V5 `GET /v5/market/instruments-info` указывает `category` в объекте `result`, а строки в `result.list` описывает отдельно; в примере linear-строки поле `category` отсутствует. См. [официальную документацию](https://bybit-exchange.github.io/docs/v5/market/instrument).

Исторический загрузчик ранее требовал `category` внутри каждой строки, хотя архив хранит её на верхнем уровне снимка. Теперь он использует проверенную категорию конверта как значение для строки, только если строка сама не содержит category. Если row-level category присутствует и противоречит envelope, она не перезаписывается и snapshot отклоняется.

Дополнительно усилена валидация `symbol` на границе обоих сборщиков: нестроковые и пустые символы больше не преобразуются в строки. Builder стандартного snapshot также проверяет тип каждой строки и символа.

- Сборщики: [8c04cde](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/8c04cde99b20fc6a42908c620e1786bb0231a6f7), [ff7e5bb](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/ff7e5bbda19907ef11b70695e0109cf90958a19e).
- Регрессионные тесты сборщиков: [f7ef140](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/f7ef1405013e0593f045b5c6f8de19fa9749c5d2), [c9096a7](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/c9096a7ccb2fd9b3b3a48537a709907529ec3c62).
- Category-envelope history fix: [c069075](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/c06907551c4210ed09540f77115fd218778676a3); regression tests [3025039](https://github.com/nikitanecilli-bit/bybit-trading-bot/commit/302503937f47277ab0ee7a83c2a0247bcf51a81c).
- Research CI for the full latest change set is being verified; results will be recorded after completion.

Эти изменения касаются только парсинга и офлайн-валидации снимков. Они не создают фактический Bybit snapshot и не подтверждают историческую полноту данных.
