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

## ENG-DATA-013 — регрессия point-in-time выбора торговых ограничений

- Расширен `tests/test_instrument_spec_history.py`: два последовательных снимка различаются не только `tickSize`, но и `minPrice`, `qtyStep`, `minOrderQty`, `minNotionalValue`, `maxLeverage`, `leverageStep`.
- Тест проверяет каждое поле до и после границы `fetched_at`: до границы возвращаются прежние ограничения, начиная с неё — новые. Это подтверждает, что lookup не смешивает поля из разных версий снимков и не использует будущие значения для прошлого.
- Существующий regression test сохраняет правило: `as_of` внутри окна сбора не использует ещё не завершённый снимок; выбирается предыдущий завершённый снимок.
- Research CI [#41902137997](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41902137997): **SUCCESS**. Новые проверки `Test as-of instrument spec history` прошли; полный job завершился успешно.
- Это проверка исторического выбора snapshot-версий, а не доказательство, что публичные snapshots достаточно частые или что биржа предоставляла каждое ограничение в точный момент сделки. Исторические значения между снимками неизвестны; интерполяция и перенос назад запрещены.
- Только offline regression tests. Никакие API requests, collectors, archive downloads, live orders или market PnL tests не запускались.

## ENG-DATA-014 — point-in-time выбор risk tiers

- Добавлен regression test для двух dated risk-limit snapshots. На границе `fetched_at` проверяются `riskLimitValue`, `maintenanceMargin`, `initialMargin`, `maxLeverage` и `mmDeduction`; lookup должен использовать только соответствующую версию tier ladder.
- Первый тестовый fixture ошибочно запрашивал position value, которая попадала во второй tier старого снимка, где leverage 80 уже запрещён. Исправлен именно fixture: position value помещена внутрь первого tier; production logic не менялась.
- Research CI [#41902627575](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41902627575): **SUCCESS**, полный job завершился успешно. Проверка `Test as-of Bybit risk-tier history and selection` прошла.
- Результат подтверждает выбор сохранённого снимка по `fetched_at`, но не покрывает неизвестные изменения risk tiers между снимками. Не выполняется интерполяция и не предполагается, что снимок атомарен на стороне биржи.
- Только offline tests; API, collectors, архивы, live orders и market PnL tests не запускались.

## ENG-DATA-015 — согласование instrument specs и risk tiers по времени

- Добавлен `bybit_market_state.py` с `get_linear_market_state()`: единая точка получения linear instrument spec и полной risk-tier ladder для одного `as_of_ts`.
- Компонент выбирает только последние завершённые снимки не позже `as_of_ts`; будущие снимки не используются. Обязателен явный бюджет `max_snapshot_skew_ms`; при превышении разницы между `fetched_at` инструментов и risk tiers функция завершается fail-closed. Опционально задаются независимые пределы давности каждого источника.
- Возвращаемая структура содержит оба времени наблюдения и `snapshot_skew_ms`, чтобы downstream-код мог сохранять provenance. Для instrument spec сохраняется проверка статуса Trading; для risk tiers возвращается полная лестница.
- Добавлены 5 offline tests: успешное согласование в пределах skew budget, превышение skew, будущий risk snapshot, stale risk snapshot и валидация skew budget.
- Research CI [#41903071454](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41903071454): **SUCCESS**, 59/59 шагов.
- Важное ограничение: `fetched_at` — время завершения клиентского сбора, не общий серверный snapshot token. Даже нулевой skew не доказывает атомарность ответов Bybit или синхронность данных внутри последовательной пагинации. Порог skew должен быть обоснован отдельно; здесь не назначается произвольное production-значение.
- Только offline CI. Реальные API requests, collectors, archive downloads, live orders и market PnL tests не запускались.

## ENG-DATA-016 — аудит подключения согласованного market state

- Усилен `get_linear_market_state()`: проверяются непустой symbol и тип/знак обоих max-age budgets; `bool`, float и отрицательные значения отклоняются. Для instrument lookup явно требуется статус `Trading`.
- Добавлены 2 offline tests на некорректные max-age budgets и пустой symbol.
- Аудит runtime path обнаружил, что `Bybit_Trading_Engine_v14_research.py` по-прежнему отдельно вызывает `InstrumentSpecHistory.get_spec()` при проверке/размере entry, `RiskTierHistory.calculate_margin_requirements()` при risk-margin проверке и `RiskTierHistory.get_tiers()` при mark-price liquidation check. H1 runner использует instrument history для tick rounding; одновременно передаёт обе директории в engine, но пока не вызывает `get_linear_market_state()`.
- Поэтому согласованный join пока является отдельным проверенным API, а не обязательным runtime guard. Нельзя утверждать, что временной skew уже ограничен во всех entry/liquidation путях. Автоматическое включение без явно утверждённого skew budget означало бы выбор произвольного порога; это не сделано.
- Research CI [#41903447996](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41903447996): **SUCCESS**, полный job завершён; 59 шагов, ошибок нет. Включает compile, deterministic tests и offline checks.
- Только offline CI и чтение исходников. Реальные API requests, collectors, archive downloads, live orders и market PnL tests не запускались. Стратегические execution/PnL gates остаются BLOCKED.

## ENG-DATA-017 — runtime enforcement of joined market state

- `UnifiedQuantEngine` теперь использует `get_linear_market_state()` перед sizing entry, когда одновременно загружены instrument specs и risk tiers. Спецификация для tick/lot sizing берётся из joined state; age limits и skew budget передаются явно. Ошибка join, включая отсутствующий skew budget, отклоняет entry до открытия позиции.
- При liquidation-aware расчёте, если доступны обе истории, risk-tier ladder берётся из joined state; отдельный `get_tiers()` в этом пути больше не используется. Это сохраняет point-in-time selection для as-of timestamp расчёта и не допускает применения будущего снимка.
- Добавлен параметр движка `max_market_state_skew_ms`, без значения по умолчанию. Для H1 replay он задаётся через `BYBIT_MAX_MARKET_STATE_SKEW_MS`; отсутствие переменной означает fail-closed отказ на entry/ошибку при joined liquidation path. Допустим только неотрицательный integer; ноль разрешает только одинаковые client-observed completion timestamps.
- Для совместимости изолированные режимы с единственным источником (только instrument specs либо только risk tiers) сохраняют прежний независимый as-of/age guard; они не дают гарантии межисточникового skew. H1 execution replay передаёт обе директории и использует общий join. Live/PnL gate остаётся заблокированным.
- Regression tests: H1 env budget parser; entry передаёт budget в joined helper; liquidation path fail-closed при отсутствующем budget. Первый CI запуск выявил фиктивный engine fixture, не учитывавший новый joined contract; fixture исправлен и повторный полный CI завершился успешно.
- Research CI [#41904156219](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41904156219): **SUCCESS**, 59/59 шагов. Проверен code commit `9e16de8f7433359955c758f159d47dcf4cbe8503`.
- Только deterministic/offline CI. Реальные API requests, collectors, archive downloads, live orders и market PnL tests не запускались.

## ENG-DATA-018 — аудит обходных путей, восстановления и повторной оценки позиций

- Закрыт разрыв entry margin: когда instrument и risk histories доступны вместе, `calculate_margin_requirements_from_tiers()` рассчитывает IM/MM непосредственно по `risk_tiers` из уже согласованного `BybitLinearMarketState`. Независимый повторный выбор risk snapshot больше не выполняется. Сохранён независимый fallback только для конфигурации без instrument history; такая конфигурация не даёт межисточниковой гарантии.
- H1 multi-bar limit-wait wrapper ранее отдельно запрашивал instrument spec. Теперь `resolve_h1_limit_wait_spec()` требует обе истории и получает tick/lot spec из joined state с теми же explicit age/skew budgets. Отсутствие одной истории или допустимого skew budget — отказ, без fallback.
- Bybit public H1 holdout runner ранее создавал движок без датированных instrument/risk snapshots. Теперь runner требует `--instrument-specs-dir`, `--risk-tiers-dir`, `--max-market-state-skew-ms` и передаёт их в движок. Это только offline входные архивы; сам runner не запускается в этой сессии.
- Восстановленные pending orders не считаются свежими: `_try_fill_pending()` разрешает исполнение только на строго ожидаемом следующем баре относительно сохранённого `signal_ts`; тест подтверждает удаление просроченного restored signal без открытия позиции.
- Восстановленные open positions не используют сохранённые при входе tier поля как доказательство текущего состояния рынка. При включённой liquidation-aware mark оценке `_liquidation_exit_price()` заново запрашивает joined state на текущий `as_of_ts`; несовпадение/устаревание/skew приводит к отказу от расчёта, не к старым tiers. Без mark-price liquidation model этот механизм не заявляется как активный.
- Остальные найденные runner'ы `run_e11`, `run_e13`, `run_uploaded_dataset_backtests`, `run_h1_limit_fill_stress`, `run_h1_walk_forward` используют Binance OHLCV proxy или диагностические данные без Bybit dated execution metadata. Они остаются research-only и не являются подтверждением Bybit execution realism; не запускались.
- Regression tests: helper расчёта IM/MM из joined ladder, engine entry не делает независимый risk-history re-query, H1 limit-wait resolver использует joined state/явный skew и отказывает без двух историй, Bybit holdout runner требует dated metadata и budget, restored stale pending сигнал удаляется.
- Research CI [#41905635534](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41905635534) запущен для code commit `a0ed6fe0a6058be57a85ae558ad32ab7e7971c52`; итог будет отражён после завершения. Предыдущий code/test baseline [#41905369230](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41905369230) завершился SUCCESS, 59/59.
- Только исходниковый аудит и offline/deterministic CI. Реальные API requests, collectors, archive downloads, live orders и market PnL tests не запускались. Все strategy/execution/PnL gates остаются BLOCKED.


## ENG-DATA-019 — совместный аудит полноты и временного skew архивов

- `audit_instrument_snapshot_coverage.py` расширен совместным offline аудитом linear instrument specs и risk-tier snapshots. Он использует те же строгие history loaders, что и runtime, и перебирает все уникальные пары снимков, выбираемые as-of логикой на объединении временных границ двух историй.
- Для каждой пары отчёт содержит оба `fetched_at`, skew, возраст обоих снимков на границе, число Trading symbols, число risk-tier symbols, долю Trading symbols с risk tiers, отсутствующие/лишние символы и распределение числа tier levels на покрытый инструмент.
- Отсутствие любой из двух историй явно даёт `joint_linear_market_state.status=INCOMPLETE`; отдельный верхнеуровневый статус `NO_DATA` сохраняет смысл отсутствия исходных JSON. Ни один skew threshold не выводится автоматически: наблюдавшийся максимум не является доказательством безопасной свежести, биржевой атомарности или приемлемого риска.
- Добавлены fixtures: три последовательные as-of пары с разными skew и потерей ETHUSDT risk tiers на последнем снимке; проверка неполного набора архивов. Аудит не делает сетевых запросов.
- Ветка на момент запуска не содержит JSON snapshots в `data/universe_history/linear/`, `data/instrument_specs/linear/` и `data/instrument_specs/risk_limits/linear/`. Выполненный в CI реальный offline audit напечатал `status=NO_DATA`, обе joined history counts = 0, `joint_linear_market_state.status=INCOMPLETE` и `skew_budget_recommendation_ms=null`. Значит статистику skew, cadence, snapshot ages и symbol coverage пока нельзя оценить.
- Research CI [#41906317729](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41906317729): **SUCCESS**, 59/59 шагов; 16/16 тестов offline temporal coverage audit прошли, включая новые joined-audit fixtures. Проверенный code commit: `dd2139445a4b5daa1c4b6238b3a2937c616f339c`.
- Только offline audit и CI. Реальные API requests, collectors, архивные загрузки, live orders и market PnL tests не запускались. Временной skew budget не выбран; strategy/execution/PnL gates остаются BLOCKED.

## ENG-DATA-020 — временная трассировка Bybit risk-tier pagination

- `scripts/snapshot_bybit_risk_limits.py` теперь сохраняет `collection_started_at` до первого запроса и `page_observations` для каждой страницы risk-limit: sequential `page_index`, client-side `request_started_at` / `request_completed_at`, `tier_count`, `symbol_count`, sorted unique `symbols` и `has_next_page`.
- Completion timestamp фиксируется после возврата `_request_page`, то есть после чтения/JSON parsing и проверки response shape/retCode. Это клиентская граница завершения обработки, не socket receipt timestamp и не серверное event time. Между страницами сохраняется фактическая последовательность запросов; сырые opaque cursors намеренно не записываются.
- Builder валидирует миллисекундные UTC-времена, границы collection window, хронологию, sequential page indexes, continuation chain, уникальность/сортировку символов внутри страницы и точное совпадение объединения page symbols с символами в финальном tier snapshot. `tier_count` сохраняет количество tier rows, поскольку один символ закономерно может иметь несколько risk tiers; `symbol_count` считает уникальные символы.
- Offline auditor теперь отдельно читает `data/instrument_specs/risk_limits/linear`, проверяет совместимость `symbol_count` / `tier_count`, временные границы, пагинацию, суммы tier rows, полноту объединения символов и повторные появления символов на разных страницах. В общий отчёт включены cadence, collection duration, межснимочные gaps, overlap и page request duration distribution. Старые schema-v1 risk snapshots без optional `collection_started_at`/`page_observations` остаются читаемыми.
- Regression coverage: `tests/test_snapshot_bybit_risk_limits.py` — page metadata, collection bounds, missing continuation и symbol mismatch; `tests/test_audit_instrument_snapshot_coverage.py` — risk page timing/tier count и fail-closed при пропущенном continuation.
- Research CI [#41907221646](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41907221646): **SUCCESS**, 59/59 workflow steps. В частности, risk-limit collector suite — 18 tests OK; combined snapshot temporal audit suite — 18 tests OK. Code commit: `4e019ea19b3515f441be70d81be88d602d10df24`.
- Сам сборщик в этой сессии не запускался, сеть и Bybit API не использовались, архивы не скачивались. Реальные page timings и completeness пока отсутствуют; `max_market_state_skew_ms` не выбран. Наблюдаемые клиентские времена не доказывают атомарность backend snapshot. Strategy/execution/PnL gates остаются BLOCKED.
### ENG-DATA-020 — дополнительная проверка итогового количества tier rows

- Builder дополнительно сверяет сумму `tier_count` по всем page observations с `len(validated_snapshot_tiers)`. Это не самосравнение метаданных страниц: ожидаемое значение берётся из реально проверенных строк финального snapshot.
- Добавлен regression test на расхождение page tier total и фактического числа tier rows. В ходе CI были обнаружены и исправлены два дефекта: первоначальное самосравнение суммы наблюдений и пропущенный аргумент `expected_tier_count` в builder call site.
- Итоговый Research CI [#41908375736](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41908375736): **SUCCESS**, 59/59 шагов, code head `e05e070b02bf3a8785a317600f466c9ce1207fda`. Это итоговая проверка исправленного кода; предыдущие промежуточные failed runs не считаются успешными.
- Offline risk-tier auditor проверяет page tier totals, временные границы, sequential indexes, continuation chain, уникальность/сортировку символов, объединение page symbols и final snapshot, request durations и collection-window overlap.
- Только offline tests и CI; ручной запуск collector, Bybit API, архивные загрузки, live orders и market PnL не выполнялись. `MAKER_EXECUTION_REALISM` и strategy/execution/PnL gates остаются BLOCKED.


## ENG-DATA-021 — runtime loader валидирует временную метаинформацию risk-tier snapshots

- Статическая проверка выявила, что ``RiskTierHistory.from_directory`` валидировал risk-tier rows и as-of timestamps, но игнорировал optional ``collection_started_at`` и ``page_observations``, даже если они присутствовали и были некорректны.
- Runtime loader теперь проверяет ``collection_started_at <= fetched_at``; если ``symbol_count`` присутствует — сверяет его с уникальными символами; если присутствуют page observations — требует их непустой список и collection start, точную схему, последовательные page indexes, корректную хронологию/границы, page continuation, уникальные отсортированные symbols, symbol/tier counts, union page symbols == snapshot symbols и сумму page tier counts == реальному числу tier rows.
- Legacy schema-v1 snapshots без optional collection/page metadata остаются совместимыми; новая проверка применяется к metadata, когда они присутствуют. Это закрывает разрыв между валидатором сборщика/offline auditor и runtime history loader, который потребляет архивы.
- Regression test проверяет валидный page metadata, отклонение неверной суммы tier rows и collection start после fetched_at. Существующие тесты продолжают проверять загрузку старых снимков без optional metadata.
- Research CI [#41908898109](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41908898109): **SUCCESS**, 59/59 шагов, tested code HEAD ``1cc503608a238141a70b6ab8f8cb81ef0824ad3b``.
- Только offline unit tests/CI. Сборщик, Bybit API, архивные загрузки, live orders и market PnL не запускались. Никакие execution/PnL gates не изменялись.


## ENG-DATA-022 — runtime loader валидирует pagination metadata instrument snapshots

- Статический аудит показал аналогичный разрыв в ``InstrumentSpecHistory.from_directory``: ``collection_started_at`` уже проверялся, но присутствующий ``page_observations`` не проверялся runtime loader-ом.
- Runtime loader теперь при наличии page observations требует collection start и проверяет точную схему полей, разрешённые status filters для категории (linear/inverse: PreLaunch, Trading, Settling, Delivering, Closed; spot: Trading; option: PreLaunch, Trading, Delivering, Closed), порядок и непрерывность status groups, последовательные page indexes, хронологию и границы времени, row_count/symbols, отсутствие повторов внутри страницы, continuation flags и точное совпадение объединения page symbols с итоговым snapshot.
- Legacy snapshots без ``page_observations`` остаются совместимыми. Добавлены regression tests на корректный набор страниц, пропущенный status group и неверный порядок status groups.
- Первый CI выявил off-by-one в runtime проверке порядка status groups; исправлена формула ожидаемого индекса группы. Итоговый Research CI [#41909339669](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41909339669): **SUCCESS**, 59/59 шагов, tested code HEAD ``794d1ca3ab57511559e2513436147c7583a1c555``.
- Только offline unit tests/CI. Collector, Bybit API, архивные загрузки, live orders и market PnL не запускались. Strategy/execution/PnL gates остаются BLOCKED.


## ENG-DATA-023 — проверка восстановленных open positions по entry-time market state

- Аудит Plan B recovery обнаружил, что UnifiedQuantEngine восстанавливал open_positions из backup и сразу продолжал работу, не перепроверяя сохранённые execution/risk provenance относительно датированных Bybit histories.
- После восстановления позиций движок теперь вызывает _validate_restored_positions_market_state(). Если обе истории доступны, для каждой позиции выполняется get_linear_market_state() по сохранённому entry_ts, с теми же explicit max_market_state_skew_ms и независимыми max-age budgets. Ошибка выбора снимков, отсутствие допустимого skew budget, будущие/устаревшие снимки или отсутствие инструмента со статусом Trading останавливают recovery через исключение.
- Проверяется сохранённый leverage по entry-time instrument spec; затем полная risk-tier ladder из того же joined state повторно рассчитывает tier ID, risk limit, MMR, deduction, tier max leverage, initial margin и maintenance margin. Отсутствующая provenance или несовпадение любого сохранённого значения приводит к отказу восстановления, а не к молчаливому принятию backup.
- Если настроен только один из двух источников, новая cross-source проверка не заявляется и не выполняется: такой legacy режим не гарантирует межисточниковый skew. Для joined H1 конфигурации отсутствие skew budget приводит к fail-closed поведению через get_linear_market_state().
- Добавлены три regression tests в tests/test_state_persistence.py: корректный joined as-of вызов с исходным entry timestamp и обоими age budgets; отклонение несовпадающего risk tier; отклонение backup без entry risk-tier provenance.
- Первый CI запуск выявил только синтаксическую ошибку в многострочном with patch тестовом fixture; она исправлена. Итоговый Research CI [#41911026900](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41911026900): **SUCCESS**. Также перед ним успешно проверены commits с реализацией метода и подключением recovery hook: [#41910745821](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41910745821) и [#41910795571](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41910795571).
- Ограничения: проверка сверяет entry-time leverage и risk-margin provenance; она не доказывает атомарность Bybit snapshots и не восстанавливает неизвестные изменения между снимками. Изолированные single-source режимы остаются без межисточниковой гарантии. Legacy backups без обязательных risk provenance в joined режиме будут отклоняться.
- Только deterministic/offline tests и CI. API requests, collectors, archive downloads, live orders и market PnL не запускались. main не менялся; PR #4 и PR #13 не слиты; strategy/execution/PnL gates остаются BLOCKED.
