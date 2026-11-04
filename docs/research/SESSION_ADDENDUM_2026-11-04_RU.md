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

## Дополнение — временная семантика instrument snapshots и lifecycle

- Снимок собирается несколькими запросами/страницами; это интервал, а не атомарное наблюдение. Сборщики сохраняют `collection_started_at`, а `fetched_at` остаётся временем завершения полного снимка. As-of выбор консервативно использует только полностью завершённые снимки; снимок, сбор которого ещё шёл на момент `as_of`, не выбирается.
- Исторические файлы без `collection_started_at` остаются читаемыми; точное окно их сбора неизвестно.
- `deliveryTime=0` в официальном примере Bybit для perpetual означает отсутствие фиксированной даты доставки. Код трактует его как открытый lifecycle только для `Trading` LinearPerpetual. Для `Closed`, `Settling` или `Delivering` без положительной границы запись исключается из исторической выборки, а не получает вымышленную дату завершения.
- Timestamp parser теперь принимает только десятичную строку или integer JSON value; bool, float, whitespace, знак и дробные строки отклоняются.
- Изменения интервала сбора: `7e211c7`, `df4cbad`, `8ba2475`; тесты: `28b117e`, `0eb0b9e`, `8e03e83`, `ba410ba`.
- Lifecycle parsing: `f3be0b7`; regression tests: `e2a3df8`; syntax correction: `b32b823`; CI path-filter fix: `5296c5a`; parser contract test: `2bfcd82`. Первый CI #41894908409 поймал незакрытую docstring в lifecycle helper; исправлено в `b32b823`. Повторные Research CI #41895045876 и #41895062773 завершились SUCCESS; второй запуск включает все изменения на `2bfcd82`. В workflow добавлен path `scripts/snapshot_bybit_linear_universe.py`.
- Основание API-семантики: [официальная документация Bybit Get Instruments Info](https://bybit-exchange.github.io/docs/v5/market/instrument), где `deliveryTime` описан как delivery time для expired futures и delisting time для perpetual; официальный пример LinearPerpetual показывает `deliveryTime: "0"`.
- Никакие live/private API запросы, collectors, новые archive downloads, рыночные PnL-тесты или ордера не запускались.

## ENG-DATA-008 — статус инструмента не равен исторической торгуемости

- Статический аудит `scripts/snapshot_bybit_linear_universe.py`, `instrument_spec_history.py` и offline tests завершён.
- `is_linear_usdt_perpetual_within_lifecycle_at()` проверяет только границы launch/delivery. Тест намеренно считает `Closed` контракт внутри lifecycle до `deliveryTime`; docstring прямо запрещает трактовать это как проверку непрерывной торгуемости.
- `InstrumentSpecHistory.get_spec()` не переносит сегодняшнее состояние назад во времени: он выбирает последний завершённый snapshot с `fetched_at <= as_of_ts` и по умолчанию требует, чтобы статус в этом snapshot был `Trading`. Отсутствующий в последнем полном snapshot символ приводит к отказу.
- Ограничение: snapshot — точечное наблюдение, не журнал переходов статуса. Между снимками невозможно восстановить временную приостановку, смену статуса или момент появления нового символа. `max_age_ms` необязателен и по умолчанию не ограничен; даже ограничение возраста не доказывает отсутствие перехода статуса внутри интервала.
- Вывод: явного ретроактивного применения текущего статуса не обнаружено; as-of выборка по датированным снимкам устроена правильно. Но точный исторический tradable universe не доказан без частоты наблюдений и/или авторитетных событий смены статуса.
- Не стал менять lifecycle predicate и не стал вводить произвольный default для freshness. Оставить историческую торгуемость и PnL gate заблокированными до подтверждения покрытия статусов и sampling gaps.
- Документировано в `docs/audits/POINT_IN_TIME_UNIVERSE_AND_ARCHIVE_AUDIT_2026-11-03.md`; commit `371d989`. Это только документация, без запуска collectors/API/market tests и без новых архивов.

- Regression guard: `tests/test_instrument_spec_history.py::test_later_status_is_not_applied_retroactively_to_earlier_as_of` confirms a later `Closed` snapshot does not rewrite the earlier `Trading` observation; at the later snapshot timestamp, `require_trading=True` rejects it. Test commit `1eb1234`.
- Research CI [#41896360159](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41896360159): **SUCCESS**, all 56 job steps completed successfully. This includes offline instrument-history tests, deterministic checks, and the existing-archive provenance scan; it does not represent a live Bybit API request, a collector run, a new archive download, or a market PnL experiment.

## ENG-DATA-009 — аудит временного покрытия снимков

- Workflow audit подтверждён по трём YAML: Bybit linear universe, instrument specs и risk tiers запускаются только вручную ('workflow_dispatch'); расписания нет.
- В текущем checkout отсутствуют JSON snapshots в 'data/universe_history/linear/' и 'data/instrument_specs/linear/'. Offline audit в Research CI вернул 'NO_DATA', поэтому cadence/gap нельзя численно оценить.
- Добавлен 'scripts/audit_instrument_snapshot_coverage.py': считает число снимков, временной охват, длительность collection window, интервалы между завершением предыдущего снимка и началом следующего (или completion-to-completion для legacy файлов), overlap окон, добавленные/удалённые символы и наблюдаемые смены статусов. Нет произвольного freshness threshold; пользовательские '--max-gap-hours' и '--max-collection-minutes' опциональны. Overlap окон, malformed snapshot и duplicate fetched_at завершают аудит ошибкой.
- Добавлено 9 offline regression tests: пустой архив, cadence, duration, символы/status changes, legacy timestamps, overlap, duplicate timestamps и явные thresholds.
- CI workflow включает compile, тесты и offline audit. Research CI [#41897629817](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41897629817): **SUCCESS**; все 58 шагов прошли. Включённый audit честно сообщил 'NO_DATA'.
- В процессе CI две проблемы тестового harness были пойманы и исправлены: отсутствовал repository root в 'sys.path', затем неверно ожидалась максимальная длительность двух разных fixture windows. После исправлений suite прошёл.
- Не включал schedule и не dispatch-ил collectors: нет подтверждённого доступа/разрешённого пути получения snapshot. Никакие API requests, collector runs, archive downloads, market tests или PnL не выполнялись.

## ENG-DATA-010 — отметки времени по каждой странице Bybit

- Оба snapshot collector теперь записывают опциональный `page_observations`: status filter, page index, начало запроса, завершение клиентской обработки ответа, число строк, список символов и признак следующей страницы.
- `request_completed_at` ставится после `_request_page` (включая JSON parse и проверку retCode/формата). Это верхняя граница клиентского запроса, не timestamp события на стороне Bybit и не точное время приёма сетевого пакета. Opaque pagination cursor не сохраняется.
- Builder проверяет хронологию, последовательность страниц по каждому фильтру, границы общего collection window и совпадение объединения символов страниц с итоговым universe. Старые schema-v1 снимки без `page_observations` остаются совместимыми.
- Offline auditor проверяет метаданные страниц и выдаёт per-status page counts/windows/row counts и распределение длительности запросов.
- Research CI [#41898947956](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41898947956): **SUCCESS**, 59/59 шагов. Включает compile, tests collectors, tests temporal audit, offline audit. Промежуточный CI упал на тесте верхней границы времени, поскольку linear-universe builder ещё не передавал page metadata общему валидатору; исправлено в `d2edd46`, затем успешно перепроверено в #41898525899 и #41898947956.
- Ограничение: это сужает окно неопределённости до отдельного запроса, но не раскрывает точный момент выборки данных backend Bybit и не фиксирует переходы статуса между запросами. Снимок остаётся последовательным наблюдением, не атомарным exchange-side universe.
- Ни публичные/приватные API-запросы, ни collectors, ни скачивание архивов, ни рыночные/PnL-тесты не запускались.

## ENG-DATA-011 — контроль целостности пагинации и status filters

- Валидация требует `has_next_page=true` у каждой промежуточной страницы и `false` у последней страницы соответствующего фильтра. Это выявляет оборванную цепочку и ложное завершение пагинации.
- Группы фильтров должны быть непрерывными и идти в ожидаемом порядке; каждый ожидаемый фильтр обязан присутствовать, даже если API вернул пустую страницу.
- Instrument-spec collector теперь отвергает строку, чей `status` не совпадает с запрошенным статусным фильтром.
- Offline audit считает повторные появления символов между страницами и выводит `duplicate_symbol_observations`. Идентичные дубликаты пока остаются дедуплицируемыми (как и прежде), конфликтующие записи отвергаются. Повторы — сигнал качества, но не доказательство пропусков.
- Добавлены регрессии для отсутствующей continuation page, неверного флага последней страницы, пропущенного фильтра, перемешанных групп, ответа с неправильным статусом и повторных символов.
- Research CI [#41900677467](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41900677467): **SUCCESS**, 59/59 шагов. Включены collector tests, temporal audit tests и offline audit.
- Важное ограничение: это подтверждает внутреннюю согласованность клиентской записи пагинации, но не атомарность backend Bybit. При отсутствии server-side snapshot token и точных event timestamps невозможно доказать, что изменяющийся многостраничный ответ не пропустил инструмент между страницами.
- API, collectors, загрузки архивов и PnL/market tests не запускались.

## ENG-DATA-012 — идентичность контракта между снимками

- Исторический loader больше не считает `symbol` достаточным идентификатором. Для linear-контракта обязательны непустые `contractType`, `baseCoin`, `quoteCoin`, `settleCoin`.
- Составной identity tuple сохраняется рядом со спецификацией. Если символ повторно появляется в любой более поздней точке истории с другим tuple (даже после одного или нескольких снимков, где его не было), загрузка завершается ошибкой. Два разных символа с одинаковым tuple в одном снимке также отклоняются как неоднозначность.
- Если tuple совпадает, а символ между соседними полными снимками изменился, `possible_renames` сообщает `possible_rename_not_proven`. Автоматического alias, склейки или переписывания истории нет.
- Изменения tickSize/lotSize/leverage constraints не считаются сменой идентичности, если составной tuple стабилен.
- Регрессии: повторное использование символа, повторное использование после пропуска снимка, возможное переименование без слияния, дублирующийся tuple, отсутствие обязательных identity-полей и нормальное изменение торговых ограничений.
- Первые CI-запуски выявили неполный старый fixture в round-trip тесте collector→history loader. Добавил контрактные identity-поля в fixture. Итоговый Research CI [#41901402434](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41901402434): **SUCCESS**, 58/58 шагов.
- Ограничение: этот tuple — консервативный составной ключ из публичных полей Bybit, а не гарантированный биржей immutable contract ID. Поэтому одинаковый tuple при смене символа только помечается как возможное переименование; автоматического объединения нет.
- API, collectors, архивы, live orders и рыночные/PnL-тесты не запускались.


## ENG-DATA-012 — идентичность инструмента в истории снимков

В `instrument_spec_history.py` добавлена составная идентичность linear-контракта из `contractType`, `baseCoin`, `quoteCoin`, `settleCoin`. Повторное появление того же `symbol` с изменившейся идентичностью отклоняется по всей загруженной истории, в том числе если между снимками были пропуски. Два разных символа с одной идентичностью внутри одного снимка считаются неоднозначностью и отклоняются. Изменения торговых ограничений (tick/lot/leverage) не считаются сменой идентичности.

Изменение `symbol` при сохранении составной идентичности записывается в `possible_renames` как `possible_rename_not_proven`; поиск теперь работает и через промежуточные снимки, где инструмент отсутствовал. Это только сигнал для ручной проверки: алиасы не создаются, исторические данные не объединяются. Добавлены regression tests для повторного использования символа, пропуска снимка, возможного переименования, дублирующей идентичности и отсутствующих полей.

CI: run [41901402434](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41901402434) SUCCESS, 59/59 шагов для коммита `a72936fa03d3cd3a960a76038f01e853dd8b3514`. Последующее расширение проверки переименований через пропуски требует отдельного CI run; до его завершения не считается проверенным.
