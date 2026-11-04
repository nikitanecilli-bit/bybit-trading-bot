# ENG-RECON-001 — Read-only Bybit exchange reconciliation contract

Дата: 2026-11-02  
Статус: DESIGN / BLOCKED — do not enable live resume.

## Цель

Определить минимальный доказуемый протокол сверки локального backup с фактическим состоянием Bybit перед любым восстановлением торговли. Этот документ не добавляет сетевых вызовов, не читает секреты и не меняет торговые endpoint'ы.

## Подтверждённые ограничения текущей модели

В `OpenPositionState` есть `size_usdt`, `risk_usdt`, `direction`, `entry_price`, `entry_ts`, но нет:
- фактического биржевого количества контрактов `qty`;
- `positionIdx` / подтверждённого режима позиции (one-way или hedge);
- Bybit `orderId`, `orderLinkId`, `execId` и журнала частичных исполнений;
- подтверждённого exchange-side stop/TP state.

Локальный `pending` — это сигнал на следующий бар, а не доказательство существующего биржевого ордера. Нельзя сравнивать его с active orders как будто это уже отправленный ордер.

Следствие: `size_usdt / entry_price` нельзя объявлять точным exchange qty. Пока нет точного qty и идентификаторов, положительное решение RECONCILED недоступно для открытых позиций и биржевых ордеров.

## Read-only источники Bybit V5

Для текущего scope — USDT linear perpetuals, `category=linear`, `settleCoin=USDT`:

1. **Positions:** `GET /v5/position/list?category=linear&settleCoin=USDT&limit=200`, пройти все страницы по `nextPageCursor`. Нужны как минимум `symbol`, `side`, `size`, `avgPrice`, `positionIdx`, `updatedTime`, `positionStatus`.
2. **Active orders:** `GET /v5/order/realtime?category=linear&settleCoin=USDT&openOnly=0&limit=50`, пройти все страницы. Сохранить `orderId`, `orderLinkId`, `symbol`, `side`, `qty`, `leavesQty`, `cumExecQty`, `orderStatus`, `createdTime`, `updatedTime`, `positionIdx` если присутствует.
3. **Executions:** `GET /v5/execution/list?category=linear&startTime=...&endTime=...&limit=100`, пройти все страницы. Bybit ограничивает один временной интервал `endTime - startTime <= 7 дней`; большой outage window нужно разбить на непересекающиеся/стыкующиеся интервалы максимум по 7 дней и дедуплицировать граничные записи по `execId`. Сохранить `execId`, `orderId`, `orderLinkId`, `symbol`, `side`, `execQty`, `execPrice`, `execTime`, `execType`, `execFee`. Один ордер может иметь несколько execution rows; дедупликация должна быть по execution identity, не по orderId.
4. **Order history:** `GET /v5/order/history` нужен для восстановления закрытых/отменённых/отклонённых ордеров и событий, которые не гарантированно присутствуют в realtime endpoint после перезапуска сервиса.

Официальные ссылки:
- Position info: https://bybit-exchange.github.io/docs/v5/position
- Realtime/open orders + pagination/history caveat: https://bybit-exchange.github.io/docs/v5/order/open-order
- Execution list: https://bybit-exchange.github.io/docs/v5/order/execution
- Order history: https://bybit-exchange.github.io/docs/v5/order/order-list

## Обязательные проверки до любого статуса PASS

- Все ответы имеют HTTP success и `retCode == 0`; отсутствие страницы/ошибка/timeout/403/неполный cursor = UNKNOWN/BLOCKED, не пустой аккаунт.
- Снять все страницы для positions и active orders; cursor должен завершиться пустым.
- Снимки positions/orders/executions имеют временные границы и server time; при чрезмерном рассогласовании повторить read-only capture или BLOCKED.
- Scope account/category/settleCoin должен совпадать с конфигурацией. Не смешивать spot, inverse, options и linear.
- Сопоставлять позиции по `symbol + positionIdx + side`, затем exact qty, avg entry и временным/идентификационным данным. Bybit size положительный; side Buy/Sell, `positionIdx` различает one-way/hedge.
- Любая лишняя exchange position, отсутствующая local position, несовпадающая сторона/qty, unknown position mode, либо локальная позиция без exact qty/identity = BLOCKED.
- Сопоставлять активные ордера только по сохранённым exchange `orderId/orderLinkId`; сравнивать статус, остаток `leavesQty` и исполненное `cumExecQty`. Не считать локальный pending signal биржевым ордером.
- Применить execution rows после `saved_at_utc` к локальной истории только при наличии надёжного order/execution identity и точной quantity model; иначе ручная сверка/BLOCKED.
- Проверить exchange stop-loss / take-profit и позиционный режим; локальная цена стопа сама по себе не доказывает наличие защитного ордера на бирже.

## Fail-closed state machine

| Состояние | Значение | Разрешённое действие |
|---|---|---|
| `NOT_CHECKED` | Сверка ещё не выполнялась | Никакого возобновления |
| `SNAPSHOT_INCOMPLETE` | API/страницы/время неполные | Никакого возобновления |
| `MISMATCH` | Локальное и биржевое состояния расходятся | Никакого автоматического исправления; ручное расследование |
| `UNSUPPORTED_LOCAL_MODEL` | Нет exact qty/order identity/position mode | Никакого возобновления |
| `RECONCILED_READ_ONLY` | Все позиции/ордера/исполнения доказуемо совпали | Только отчёт; live resume всё равно требует отдельного операционного gate |

Ни одно состояние не должно автоматически создавать, отменять, изменять или закрывать ордера/позиции.

## Текущий вердикт

`UNSUPPORTED_LOCAL_MODEL / BLOCKED`.

Причина: research engine не хранит exact exchange qty, `positionIdx`, order IDs/link IDs или execution ledger. Существующий API-check только проверяет доступ к read-only API-key-info endpoint и не выполняет reconciliation. В GitHub Actions ранее наблюдался HTTP 403 на региональных Bybit hosts; это не основание подменять snapshot пустым состоянием.

## Следующие безопасные шаги

1. Получить подтверждённый read-only Bybit response capture для `linear/USDT` (если региональный доступ восстановится); сохранять сырые JSON, UTC capture time, cursor completion, category, response `time` и SHA-256 без секретов.
2. Добавить в локальную модель exact quantity, position mode/index и биржевые order/execution identifiers только после решения по sizing/instrument specs. Не вычислять qty из notional proxy.
3. Реализовать pure parser + deterministic fixture tests для всех response schemas, pagination, duplicate executions, empty position rows, hedge-mode pairs и partial fills.
4. Реализовать read-only comparator; сначала report-only, затем fail-closed restore gate. Никаких mutating endpoints.
5. Отдельно решить процедуру ручного восстановления при MISMATCH.

**Не запускать PnL sweeps и не разрешать live restart до закрытия этого gate.**


## Реализация первого слоя

- **ENG-RECON-002 ACCEPT:** `bybit_reconciliation.py` добавлен как pure parser для paginated V5 positions, active orders и executions. 13/13 fixture tests passed; CI #41448898597 SUCCESS.
- Парсер не делает HTTP calls, не использует ключи и не отправляет ордера. Он проверяет только переданные ему страницы, требует integer retCode=0 и непрерывную цепочку cursor; он не доказывает, что вызывающий код получил все страницы.
- Следующий слой: read-only collector with cursor loop + server-time coherence, затем report-only comparator.
- Общий статус по-прежнему `UNSUPPORTED_LOCAL_MODEL / BLOCKED`: exact local qty, `positionIdx`, order IDs/link IDs и execution ledger отсутствуют.


## ENG-RECON-003 — read-only snapshot collector (code/fixture acceptance)

Добавлен `scripts/bybit_reconciliation_snapshot.py` — сетевой collector, который имеет только GET-запросы и не содержит торговых/mutating endpoints.

Защитные условия:
- До любых account snapshot endpoints запрашивается `/v5/user/query-api`; ключ должен совпасть с переданным и иметь явный `readOnly == 1`. Иначе выполнение прекращается.
- Затем читается Bybit server time до и после capture. Время не должно идти назад; длительность окна ограничена 120 секундами.
- Credential-bearing запросы разрешены только на allowlist официальных Bybit API hosts; `_validate_base_url()` вызывается до любых запросов, HTTP redirects отключены через отдельный opener.
- Positions и active orders собираются до завершения cursor pagination; ошибка HTTP, retCode, shape или повтор cursor — BLOCKED, не пустой аккаунт.
- Execution history разбивается на интервалы не длиннее 7 суток; страницы валидируются parser'ом отдельно по каждому интервалу; итоговые события дедуплицируются по `execId`.
- Сырые ответы сохраняются в JSON вместе с capture metadata и SHA-256; запись атомарная, с fsync файла и директории на POSIX.
- CI использует только mocked transport. В workflow нет шага, который читает GitHub Secrets или обращается к Bybit. 15 collector tests + 16 parser tests + 17 report-comparator tests прошли в [Actions #41470373006](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41470373006). В collector/comparator добавлена строгая дедупликация `execId`: одинаковые записи на границе интервалов схлопываются, конфликтующие payload с тем же ID блокируют capture/report. ACCEPT относится только к коду и fixture coverage.

Текущие ограничения:
- Collector не запускался против Bybit и не создавал реальный snapshot; прежний HTTP 403 на GitHub runners остаётся неразрешённым.
- Сбор execution history не заменяет order history и проверку exchange-side stop/TP.
- Capture status — только `CAPTURED_READ_ONLY_NOT_RECONCILED`, не `RECONCILED_READ_ONLY`.
- Локальная модель всё ещё не хранит exact exchange qty, positionIdx и exchange order/execution identity. Открытые позиции/ордера остаются `UNSUPPORTED_LOCAL_MODEL / BLOCKED`.
- Реальный запуск допустим только с ключом, который Bybit сам подтверждает как read-only; тестовые фикстуры не доказывают доступность API из конкретной сети.

Реальный API capture не выполнялся. Успешный CI не подтверждает доступность Bybit API, полноту реального снимка или сверку состояния аккаунта.


## ENG-RECON-004 — report-only comparator

Добавлен `scripts/bybit_reconciliation_report.py`. Он не обращается к сети: проверяет local backup и уже сохранённый snapshot, сверяет SHA-256, строгие парсеры, counts, server-time bounds и непрерывность execution intervals; формирует диагностический отчёт по символам и направлениям.

CI: [Research engine checks #41458773696](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41458773696), SUCCESS; comparator 12/12, collector 12/12, parser 13/13 и остальные workflow suites прошли.

**Важно:** comparator намеренно не имеет ветки PASS. Он всегда возвращает `BLOCKED_UNSUPPORTED_LOCAL_MODEL`, `reconciliation_pass=false`, `live_resume_allowed=false`. Даже нулевые позиции/ордера на snapshot не разрешают resume без local execution ledger. Локальные pending signals не сопоставляются с биржевыми active orders.

Итоговый статус остаётся `UNSUPPORTED_LOCAL_MODEL / BLOCKED`: нет точного exchange qty, `positionIdx`, order IDs/link IDs и локального execution ledger; order history и exchange-side stop/TP также не проверяются. Ни live resume, ни PnL sweep не разрешены.


## ENG-RECON-005 — position-level TP/SL visibility

Parser preserves optional Bybit position fields `takeProfit`, `stopLoss`, `trailingStop`, `tpslMode`; comparator reports `EXCHANGE_STOP_CONFIGURED`, `NO_EXCHANGE_STOP` or `UNKNOWN_FIELDS_MISSING`. Official source: [Get Position Info](https://bybit-exchange.github.io/docs/v5/position). CI #41459486381 passed: parser 14/14, collector 12/12, comparator 14/14.

This is visibility into position response fields, not proof that conditional orders are healthy or will trigger. No live API snapshot was captured.

## Order-history endpoint limitation (official V5 contract)

The official [Get Order History](https://bybit-exchange.github.io/docs/v5/order/order-list) documentation states:
- `startTime` and `endTime` may span at most 7 days per request;
- in the last 7 days, closed statuses are queryable except `Cancelled`, `Rejected`, `Deactivated`;
- those statuses are queryable only within the last 24 hours;
- beyond 7 days, only orders with fills are queryable.

Therefore order history cannot be treated as a complete event journal for a long outage. It can supplement executions and current active orders, but it cannot prove that every cancelled/rejected/deactivated unfilled order has been captured across arbitrary downtime. The next collector extension must preserve this coverage limitation explicitly, not report an exhaustive order history.

Final state remains `UNSUPPORTED_LOCAL_MODEL / BLOCKED`: no exact local exchange qty, `positionIdx`, order ID/link-ID map, full execution ledger, or complete historical order journal. No live resume or PnL sweep.


## ENG-RECON-006 — historical order capture

Collector now fetches `GET /v5/order/history` in cursor-paginated intervals of no more than seven days. Raw pages and interval boundaries are hashed into the snapshot. Duplicate `orderId` rows across windows are reduced to the newest `updatedTime`; conflicting same-time records fail closed.

The snapshot records `QUERYABLE_WINDOW_ONLY_NOT_COMPLETE`. This is intentional and required by the official endpoint contract:
- closed statuses except Cancelled/Rejected/Deactivated are queryable in the last 7 days;
- Cancelled/Rejected/Deactivated are queryable only in the last 24 hours;
- beyond 7 days, only orders with fills are queryable;
- order creation/cancellation data may be delayed.

Official source: [Bybit Get Order History](https://bybit-exchange.github.io/docs/v5/order/order-list). This endpoint cannot reconstruct every unfilled cancellation/rejection across an arbitrary outage and is not a complete event journal.

Comparator validates the historical-order pages, coverage interval and metadata, reports IDs/statuses, but still never returns PASS.

CI: [Research engine checks #41460727701](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41460727701), SUCCESS; parser 14/14, collector 15/15, comparator 16/16, persistence 54/54, configured suites and secret scan passed.

No real Bybit snapshot was captured. Final reconciliation remains `UNSUPPORTED_LOCAL_MODEL / BLOCKED`: no exact local exchange qty, positionIdx, order identity map or full local execution ledger. No live resume or PnL sweep.


## ENG-RECON-007 — граница между локальным restore и биржевой reconciliation

Дата: 2026-11-05  
Статус: BLOCKED — read-only protocol verified by fixtures; no live exchange capture and no automatic resume.

### Подтверждено аудитом

- `scripts/bybit_reconciliation_snapshot.py` отправляет только GET-запросы. До account endpoints он проверяет `/v5/user/query-api`, точное совпадение API key и `readOnly == 1`; при отрицательном результате прекращает работу до чтения позиций/ордеров.
- Base URL проверяется по allowlist официальных HTTPS Bybit hosts до отправки credentials; redirects отключены. Позиции, active orders, order history и executions собираются cursor pagination; ошибка/неполная цепочка не превращается в пустой аккаунт.
- `scripts/bybit_reconciliation_report.py` проверяет raw SHA-256, schema, counts, server-time bounds и coverage intervals, но всегда возвращает `BLOCKED_UNSUPPORTED_LOCAL_MODEL`, `reconciliation_pass=false`, `live_resume_allowed=false`.
- `UnifiedQuantEngine(restore_plan_b=True)` восстанавливает локальный backup и повторно проверяет joined instrument/risk history для позиций. Этот локальный restore не является биржевой reconciliation: engine не вызывает collector/comparator и не сверяет account positions, active/conditional orders или execution history.
- Добавлен regression test `test_local_only_and_exchange_only_positions_are_both_reported`: comparator явно перечисляет локальные символы без exchange counterpart и exchange symbols без local counterpart, сохраняя безусловный BLOCKED verdict.

### CI

Research CI [#41912294316](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41912294316): **SUCCESS**, 59/59 steps; tested code commit `3fc0e6a5ff2f8f22fdb3c67dcce0b77610ab2225`.

### Операционный вывод

- Нельзя интерпретировать успешный `restore_plan_b` как разрешение возобновить торговлю на аккаунте.
- Даже `CAPTURED_READ_ONLY_NOT_RECONCILED` — это только снимок; comparator не имеет PASS-ветки.
- Реальный collector не запускался, credentials не читались, Bybit API не вызывался; нет доказанного свежего exchange snapshot.
- Никакие mutating endpoints, live orders, collectors для рыночных данных, archive downloads или market PnL tests не выполнялись.
- Следующий необходимый инженерный этап до любого live resume: разработать отдельную модель exchange execution identity (exact qty, positionIdx, orderId/orderLinkId, execId, partial fills и protection lifecycle), связать её с local persistence и только затем проектировать reconciliation-gated startup. Не выводить exchange qty из `size_usdt / entry_price`.
- Strategy/execution/PnL и live-resume gates остаются BLOCKED.


## ENG-RECON-008 — строгие типы exchange execution identity

Дата: 2026-11-05  
Статус: IMPLEMENTED AS PURE CONTRACT / NOT INTEGRATED INTO ENGINE.

Добавлен `exchange_execution_identity.py` с тремя immutable records:

- `ExchangePositionIdentity`: category/settleCoin/symbol, exact exchange qty и avg price как decimal strings, side, positionIdx, явный one-way/hedge mode, entry orderId/orderLinkId.
- `ExchangeExecutionIdentity`: уникальная execution identity (execId), order identity, symbol/side, exact fill qty/price, exchange timestamp и optional fee.
- `ExchangeOrderIdentity`: orderId/orderLinkId, symbol/side/positionIdx, original qty, leavesQty, cumExecQty, status, reduceOnly/closeOnTrigger и optional trigger price.

### Инварианты

- Decimal values сохраняются строками; binary float и расчёт qty из notional не используются.
- Position mode согласуется с positionIdx: one-way только idx=0; hedge только idx=1 или 2.
- Position qty и avg price строго положительны; execution fill qty/price строго положительны.
- Order leavesQty и cumExecQty неотрицательны, не превышают qty и вместе не превышают исходное qty.
- Order protection flags обязательны как bool в нормализованной модели; неизвестные/отсутствующие поля и лишние ключи при десериализации приводят к отказу.
- Entry order identity обязательна для записи position identity. Если позиция возникла вне известного ордера/журнала, её нельзя объявлять полностью идентифицированной.

### Границы текущей реализации

Это типизированный pure contract с сериализацией в dict и fixture tests. Он пока **не подключён** к `OpenPositionState`, backup schema, реальным order placement/fill handlers или reconciliation comparator. Нельзя считать, что существующие backup уже содержат эти идентификаторы. Нет механизма создания/обновления этих records из фактических биржевых ответов, и нет PASS-ветки reconciliation.

Tests: `tests/test_exchange_execution_identity.py` — 8 deterministic offline tests. CI status будет указан после завершения соответствующего workflow.

Никаких API calls, credentials, collectors, live orders, archive downloads или PnL tests не запускалось. Live resume и strategy/execution/PnL gates остаются BLOCKED.


## ENG-RECON-009 — persistence exchange identity + fill ledger

Дата: 2026-11-05  
Статус: локальный storage contract implemented; real execution integration отсутствует.

### Изменения

- `OpenPositionState` получил optional `exchange_position_identity`, `exchange_orders`, `exchange_executions`.
- `set_exchange_position_identity()` проверяет соответствие symbol и side локальной позиции.
- `record_exchange_order()` дедуплицирует точные повторы и допускает lifecycle updates существующего orderId (например, New -> PartiallyFilled) только если immutable identity fields не изменились: orderLinkId, symbol, side, positionIdx, original qty, reduceOnly и closeOnTrigger.
- `record_exchange_execution()` идемпотентен по execId: точный повтор игнорируется, конфликтующая запись с тем же execId отклоняется.
- При сериализации/восстановлении nested records проходят строгую типовую проверку. Повторные execId, несовпадающие symbol/side и неизвестные поля приводят к fail-closed ошибке.
- Старые backup без трёх новых ключей продолжают восстанавливаться с пустыми order/execution collections и отсутствующей position identity.

### Проверки

Добавлены тесты round-trip через Plan B backup, order lifecycle update, exact duplicate fill idempotency, conflicting execId rejection, immutable order identity и legacy backup compatibility. Research CI run #41913042156 — результат будет добавлен после завершения.

### Граница

Методы вызываются только явно кодом/тестами. Текущий движок по-прежнему симулятор и не имеет реального Bybit order placement/fill handler. Он не генерирует exchange IDs сам и не синтезирует execId из локальных сделок. Поэтому существующие позиции без записанных exchange identity остаются не сверенными; наличие этих полей не означает reconciliation PASS.

Ни API calls, credentials, collectors, live orders, archive downloads или market PnL tests не выполнялись. Live resume и strategy/execution/PnL gates остаются BLOCKED.


### ENG-RECON-010 — сверка execution ledger с order lifecycle

Дата: 2026-11-05  
Статус: IMPLEMENTED / OFFLINE TESTED.

- Каждый execution должен ссылаться на известный `orderId`: order из сохранённого списка либо entry order из `ExchangePositionIdentity`.
- Для tracked order проверяются совпадение symbol, side и непустого orderLinkId.
- Сумма известных `execQty` по orderId не может превышать `cumExecQty` этого ордера. Строгое равенство намеренно не требуется: локальная история может быть неполной, и отсутствие части fills нельзя маскировать предположением.
- Lifecycle update существующего orderId не может уменьшить `cumExecQty` или увеличить `leavesQty`; immutable поля ордера остаются неизменными.
- Добавление execution/order и обновление position identity транзакционны: при провале проверки предыдущее состояние объекта сохраняется.
- Добавлены regressions для orphan execution, side/orderLinkId mismatch, overfill sum, rollback, monotonic order updates и partial-ledger semantics.

Research CI #41913543774 — SUCCESS, 59/59 workflow steps; тест persistence включает 96 cases на этом commit.

Граница: это локальная согласованность записанного журнала, а не доказательство полноты биржевой истории. Если Bybit вернул не все execution rows, ledger может быть только нижней границей фактического fill total. Для reconciliation PASS по-прежнему необходимы полная пагинация, контроль интервалов/снимка и независимое сравнение с биржевыми позициями/ордерами. Ни API, ни live handlers, ни PnL здесь не запускались.


### ENG-RECON-011 — проверка positionIdx и направления ордеров

Дата: 2026-11-05  
Статус: IMPLEMENTED / OFFLINE CI VERIFIED.

- Если локальная позиция имеет exchange identity, каждый связанный ордер обязан иметь тот же `symbol` и тот же `positionIdx`.
- Проверка покрывает one-way (`positionIdx=0`) и hedge (`positionIdx=1/2`) identity; индекс ордера не выводится из стороны ордера. В hedge mode закрывающий Sell для long positionIdx=1 остаётся связан с индексом 1.
- Ордер на противоположной стороне от биржевой позиции требует `reduceOnly=true`; ордер на той же стороне не может быть reduce-only для этой позиции.
- `closeOnTrigger=true` требует `reduceOnly=true`.
- Добавлены тесты на несовпадающий hedge positionIdx, корректный hedge close, ошибочный reduceOnly на entry/exit и некорректный closeOnTrigger.
- Research CI #41913895096 — SUCCESS, 59/59 workflow steps.

Ограничение: правила проверяются только когда position identity известна. Для legacy backup без exchange identity данные не восстанавливаются догадками. Это локальная проверка связности ордеров, не полная верификация всех Bybit order types/position modes; реальный обменный протокол и обработчики ордеров не запускались.

Не выполнялись API calls, credentials, collectors, archive downloads, live orders или market PnL tests. Reconciliation PASS и live resume остаются BLOCKED.


### ENG-RECON-012 — несколько ордеров, частичные исполнения, отмена и замена

Дата: 2026-11-05  
Статус: IMPLEMENTED / OFFLINE CI VERIFIED.

- Журнал сохраняет каждый ордер по отдельному `orderId`; несколько параллельных выходных ордеров одной позиции не объединяются.
- Исполнения привязываются к конкретному `orderId` и `execId`; повторная доставка идентичного execution остаётся идемпотентной, конфликтующий повторный `execId` отклоняется.
- Сумма известных исполнений проверяется отдельно для каждого ордера и не может превышать его `cumExecQty`.
- Частично исполненный ордер может перейти в `Cancelled`, сохранив накопленный `cumExecQty`, при этом `leavesQty` должен стать нулём. История частичных fills остаётся привязанной к старому `orderId`.
- Замена после отмены учитывается как новый ордер с новым `orderId`; старый ордер и его fills не перезаписываются.
- Терминальные статусы `Filled`, `Cancelled`, `Rejected`, `PartiallyFilledCanceled`, `Deactivated` не могут быть изменены последующими обновлениями. Идентичный повтор терминального snapshot идемпотентен.
- Для `Filled` требуется `cumExecQty == qty` и `leavesQty == 0`; для остальных перечисленных терминальных статусов требуется `leavesQty == 0`.
- Добавлены тесты нескольких параллельных ордеров, fills на нескольких ордерах, partial-fill cancellation, replacement с новым orderId, terminal-state immutability и quantity consistency.
- Первый CI выявил неточность теста: он ожидал ошибку на точном повторе уже сохранённого terminal snapshot. Это противоречило требованию идемпотентности; тест исправлен так, чтобы принимать точный повтор и отклонять попытку изменить terminal order.
- Research CI #41914354962 — SUCCESS.

Ограничение: это проверки внутреннего журнала и последовательности принятых snapshots. Они не доказывают полноту execution history, не получают order history с биржи и не подтверждают, что все варианты статусов/замены в реальном аккаунте представлены. Реальный API, handlers, collectors, live orders и market PnL не запускались. Reconciliation PASS и live resume остаются BLOCKED.


### ENG-RECON-013 — аудит количества позиции по execution ledger

Дата: 2026-11-05  
Статус: IMPLEMENTED / OFFLINE CI VERIFIED.

Добавлен метод `OpenPositionState.audit_exchange_position_quantity(execution_history_complete=False)`:

- Суммирует исполнения на стороне позиции как входящее количество.
- Суммирует исполнения на противоположной стороне как выходящее количество.
- Рассчитывает чистое количество: `entry_exec_qty - exit_exec_qty`.
- Сравнивает результат с текущим `ExchangePositionIdentity.qty`.
- Отрицательный остаток (выходные исполнения больше входных) отклоняется.
- По умолчанию возвращает `INCOMPLETE`: неполный локальный журнал не выдаётся за совпадение.
- Только при явном `execution_history_complete=True` возвращает `MATCH` или `MISMATCH`. Этот флаг — ответственность вызывающего слоя; метод сам не доказывает полноту истории.
- Результат содержит entry/exit/net qty, snapshot position qty и signed difference как строки Decimal без float-преобразований.
- Проверены точное совпадение после частичного закрытия, неполная история, mismatch, перепродажа сверх открытого количества.
- Отдельный тест сохраняет и восстанавливает position identity и fills через Plan B backup, после чего повторный quantity audit возвращает MATCH.
- Research CI #41914734752 — SUCCESS; CI #41914915742 — SUCCESS, включая тест восстановления после перезапуска (59/59 workflow steps).

Ограничение: это локальный аудит записанных fills относительно переданного snapshot позиции. Он не устанавливает полноту execution history и не сравнивает данные с реальным аккаунтом. Нельзя передавать `execution_history_complete=True` без внешнего доказательства полного временного покрытия и пагинации истории исполнений. API, credentials, collectors, archive downloads, live orders и market PnL не запускались. Reconciliation PASS и live resume остаются BLOCKED.


### ENG-RECON-014 — атомарное объединение execution batches и поздние fills

Дата: 2026-11-05  
Статус: IMPLEMENTED / OFFLINE CI VERIFIED.

Добавлен `OpenPositionState.merge_exchange_execution_batch(executions)`:

- Принимает пакет типизированных `ExchangeExecutionIdentity`; для каждой записи применяется существующая проверка symbol, orderId, side, orderLinkId и per-order cumExecQty.
- Точный повтор `execId` учитывается как duplicate и не создаёт вторую запись; конфликтующий повтор с отличающимися полями отклоняет весь пакет.
- Любая некорректная запись откатывает весь batch: fills, добавленные ранее в том же вызове, не остаются в журнале.
- После успешного объединения журнал сортируется детерминированно по `(exec_time_ms, exec_id)`. Поэтому поздно полученный fill с более ранним exchange event time занимает правильное место в журнале.
- Метод возвращает счётчики `inserted`, `duplicates`, `total`.

Добавлены offline regressions:
- overlapping pages с повторной доставкой одного execId;
- поздний fill, пришедший после более нового события;
- quantity audit после merge: численное совпадение остаётся `INCOMPLETE` по умолчанию;
- orphan execution и конфликтующий execId отклоняют batch без частичного изменения журнала.

Research CI #41915745339 — SUCCESS, 59/59 workflow steps; протестированный commit `ec85084323363f6372952e6d783757af9d26edc7`.

Ограничения:
- Это локальная идемпотентность по execId и атомарность обновления объекта. Она не доказывает, что биржа выдала все страницы или что временные окна покрывают весь жизненный цикл позиции.
- Пустая страница, отсутствие повторов или совпадение количества сами по себе не означают полноту истории. `execution_history_complete=True` по-прежнему нельзя выставлять без независимого доказательства coverage и завершённой пагинации.
- Нет персистентного журнала page cursors/coverage windows и нет collector integration; эти задачи требуют отдельного контракта источника и не должны симулироваться локальными fixtures.

Никаких Bybit API calls, credentials, collectors, archive downloads, live orders или market PnL tests не выполнялось. Reconciliation PASS, live resume и strategy/execution/PnL gates остаются BLOCKED.


### ENG-RECON-015 — интервалы покрытия execution history

Дата: 2026-11-05  
Статус: IMPLEMENTED / OFFLINE CI VERIFIED.

Добавлен immutable контракт `ExchangeExecutionCoverage` и поле `OpenPositionState.exchange_execution_coverage`, которое автоматически сохраняется/восстанавливается через Plan B вместе с остальным состоянием позиции.

Контракт окна:
- `coverage_id` — стабильный идентификатор аттестации окна;
- `symbol` — инструмент;
- `window_start_ms`, `window_end_ms` — полуоткрытый интервал `[start, end)`;
- `page_count` — положительное число страниц;
- `pagination_complete` и `terminal_page_seen` — отдельные bool-флаги; нельзя объявить пагинацию завершённой без наблюдения terminal page.
- Точный повтор `coverage_id` идемпотентен; конфликтующий повтор отклоняется. Другая символика и неизвестные/пропущенные поля отклоняются строгим контрактом.

Добавлены методы:
- `record_exchange_execution_coverage()` — сохраняет caller-attested окно, не выводя покрытие из списка fills.
- `audit_exchange_execution_coverage(lifecycle_start_ms, audit_end_ms)` — объединяет перекрывающиеся/смежные завершённые окна, сообщает временные gaps, учитывает только окна с завершённой пагинацией и проверяет, что известные fills попадают хотя бы в одно полное окно.
- Начало аудита обязано совпадать с `position.entry_ts`; нельзя случайно получить COMPLETE, проверив только укороченный интервал.

Offline tests:
- overlapping windows дают непрерывное покрытие;
- незавершённая пагинация не закрывает gap;
- conflicting coverage ID и неверный symbol отклоняются;
- подмена lifecycle start отклоняется;
- coverage metadata сохраняется и восстанавливается через Plan B.

Research CI #41916337116 — SUCCESS, 59/59 workflow steps; протестированный commit `6b30deb3ef279ac6bc30960fc776f57f687695db`.

Критическое ограничение:
- `COMPLETE` означает только, что сохранённые caller-attested интервалы покрывают заданный lifecycle interval без разрывов, все их pagination flags заявлены завершёнными и известные fills попадают в окна.
- Этот код не проверяет фактические HTTP-запросы, server-side snapshot consistency, корректность cursor chain, задержанные биржевые события или полноту выдачи API. `pagination_complete` и `terminal_page_seen` — аттестации вызывающего слоя, а не криптографическое/биржевое доказательство.
- Нельзя выставлять `execution_history_complete=True` только на основании локального coverage audit без надёжного collector provenance и независимо проверенной пагинации.
- Нет Bybit API calls, credentials, collectors, archive downloads, live orders или market PnL tests. Reconciliation PASS, live resume и strategy/execution/PnL gates остаются BLOCKED.


### ENG-RECON-016 — проверка цепочки наблюдений страниц

Дата: 2026-11-05  
Статус: IMPLEMENTED / OFFLINE CI VERIFIED.

Усилен контракт `ExchangeExecutionCoverage`: завершённость пагинации больше не задаётся входными boolean-полями. Она выводится из сохранённой последовательности `ExchangeExecutionPageObservation`.

Каждое наблюдение содержит:
- `page_index` — индекс от нуля, строго последовательный;
- `request_started_at_ms` и `request_completed_at_ms` — client-observed временные границы запроса;
- `row_count` — неотрицательное число строк страницы;
- `has_next_page` — признак наличия следующей страницы.

Валидация цепочки:
- наблюдения должны идти с индексами 0..N-1;
- время завершения каждой страницы не может быть раньше старта;
- следующий запрос не может начаться до завершения предыдущего;
- каждая не последняя страница обязана иметь `has_next_page=true`;
- последняя страница считается terminal только при `has_next_page=false`;
- пустая последовательность страниц недопустима;
- `page_count`, `pagination_complete` и `terminal_page_seen` теперь вычисляются из page observations, а не принимаются как отдельные утверждения.

Тесты покрывают корректную цепочку, отсутствие terminal page, преждевременный terminal flag и пересекающиеся request windows. Plan B round-trip сохраняет observations.

Research CI #41916699655 — SUCCESS, 59/59 workflow steps; протестированный commit `195c3278e5791cbe12b3905b98b399ff4b9b5663`.

Ограничения:
- Метки времени request — клиентские наблюдения, а не server-side event time и не доказательство атомарного снимка.
- Наблюдения пока передаются вызывающим слоем; реальный execution collector не подключён. Контракт проверяет сохранённую последовательность, но не доказывает, что метаданные получены от настоящих HTTP-ответов.
- Сырые opaque cursors намеренно не сохраняются; нет подтверждения, что backend не пропустил/не продублировал события между страницами.
- Даже корректная terminal page chain не доказывает, что задержанные исполнения уже появились в API или что границы временного запроса полностью соответствуют lifecycle позиции.
- Реальные API, credentials, collectors, archive downloads, live orders и market PnL tests не запускались. Reconciliation PASS, live resume и strategy/execution/PnL gates остаются BLOCKED.


### ENG-RECON-017 — response provenance для read-only reconciliation pages

Дата: 2026-11-05  
Статус: IMPLEMENTED / OFFLINE CI VERIFIED.

Read-only snapshot collector теперь записывает для каждой страницы `page_provenance`:
- endpoint и page index внутри соответствующей pagination chain;
- client-observed `request_started_at_ms` / `request_completed_at_ms`;
- фактически использованные query params и их canonical SHA-256;
- SHA-256 запрошенного и следующего cursor (сами cursor остаются в существующем raw envelope);
- SHA-256 canonical JSON decoded response;
- retCode, row_count и has_next_page.

Новый capture schema — version 2. Report validator для schema v2 перепроверяет:
- точный набор provenance полей;
- endpoint и последовательность page index;
- query params против requested cursor и fingerprint;
- response fingerprint против сохранённого decoded JSON;
- next cursor fingerprint против cursor следующей страницы;
- retCode, row count, continuation flag;
- отсутствие пересекающихся/переставленных client-observed request intervals и наличие terminal page в каждой chain.
Schema v1 остаётся читаемым для backwards compatibility, но не содержит этих новых provenance guarantees.

Offline tests:
- multi-page execution collector fixture проверяет cursor chain, response/query fingerprints, row count и client timing;
- report schema-v2 принимает валидную provenance;
- изменение response fingerprint и подмена query cursor отвергаются;
- существующие schema-v1 report fixtures продолжают работать.

Research CI #41917443294 — SUCCESS, 59/59 workflow steps; tested code commit `52a492d8c9fd5582fbe52b67dc1cf9f6b168a7ed`.

Границы доказательности:
- `response_canonical_sha256` считается по canonical JSON после декодирования ответа, не по исходным HTTP wire bytes. Это проверка целостности сохранённого decoded payload, не подпись Bybit и не доказательство происхождения ответа.
- Query params и cursor fingerprints — provenance metadata; collector не сохраняет HTTP request/response headers или TLS transcript.
- Request timestamps — клиентские границы вокруг `request_json`; completion фиксируется после возврата и JSON decoding, не является точным socket receive time или server event time.
- Schema v1 snapshots остаются совместимыми, поэтому report не может требовать provenance от старых captures.
- Read-only collector не запускался вручную; CI использует FakeTransport. Реальных Bybit API calls, credentials, collector runs, archive downloads, live orders или market PnL tests не было.
- Snapshot остаётся `CAPTURED_READ_ONLY_NOT_RECONCILED`; reconciliation PASS, live resume и strategy/execution/PnL gates остаются BLOCKED.


### ENG-RECON-018 — обнаружение поздних executions между read-only snapshots

Дата: 2026-11-05  
Статус: IMPLEMENTED / OFFLINE CI VERIFIED.

В `scripts/bybit_reconciliation_report.py` добавлена чистая функция `compare_execution_snapshots(initial, refreshed)`:
- принимает два уже сохранённых snapshot с одинаковым `saved_at_utc` (одна lifecycle start boundary);
- валидирует оба snapshot существующим строгим parser-ом, raw SHA-256, интервалы, pagination chains и schema-v2 provenance, если она присутствует;
- сравнивает execution по `execId`;
- новый execId с `execTime <= initial.bybit_server_time_before_ms` классифицируется как поздно обнаруженное исполнение;
- новый execId с более поздним event time классифицируется как последующее исполнение;
- если один execId присутствует в обоих snapshots, но его identity/содержимое отличается, сравнение завершается ошибкой, а не выбирает одну версию.

Результат содержит новые и late execId, оба server-time boundary и явные неизменяемые safety flags:
`execution_history_complete=false`, `reconciliation_pass=false`, `live_resume_allowed=false`.
Отсутствие новых записей означает только `NO_NEW_EXECUTIONS_OBSERVED` в сравнённых снимках, не доказательство полноты журнала.

Offline tests проверяют:
- поздний fill, обнаруженный во втором snapshot, хотя его event time предшествует первому server-time boundary;
- конфликтующее содержимое одного execId между snapshots;
- отсутствие автоматического повышения completeness/PASS/resume.

Research CI #41917860097 — SUCCESS, 59/59 workflow steps; tested code commit `d9aeebb6bc303b497f19b7d0e524f9e7cfb0d265`.

Ограничения:
- Сравнение выполняется только над двумя caller-provided сохранёнными snapshots; повторный запрос Bybit не запускается автоматически.
- Одинаковый `saved_at_utc` необходим, чтобы сравнивать один и тот же локальный lifecycle start; более поздний snapshot должен иметь строго больший `bybit_server_time_before_ms`.
- Позднее обнаружение показывает, что первая выгрузка не содержала запись, известную при повторной выгрузке; оно не доказывает причину задержки и не даёт гарантии, что следующая выгрузка уже окончательна.
- Текущий comparator сопоставляет записи по execId и отклоняет изменившуюся identity; он не удаляет fills и не переписывает локальный execution ledger.
- Реальные Bybit API calls, credentials, collector runs, archive downloads, live orders и market PnL tests не выполнялись; CI использует offline fixtures.
- Reconciliation PASS, live resume и strategy/execution/PnL gates остаются BLOCKED.


### ENG-RECON-019 — привязка сравнения snapshots к одной учётной области

Дата: 2026-11-05  
Статус: IMPLEMENTED / OFFLINE CI VERIFIED.

Обнаружен риск: функция сравнения поздних executions принимала два валидных snapshots с одинаковым `saved_at_utc`, но не проверяла, что они получены одним API-ключом и с одного Bybit API endpoint. При ошибочном выборе файлов можно было сравнить разные аккаунты или mainnet/testnet и получить ложную дельту.

Изменения:
- Collector сохраняет `api_key_fingerprint_sha256` — SHA-256 fingerprint API key; исходный ключ и secret в snapshot не записываются.
- Snapshot schema повышена до version 3; schema v1/v2 по-прежнему доступны обычному report parser.
- `compare_execution_snapshots()` допускает только schema v3 и требует совпадения fingerprint и точного `base_url` между captures.
- Добавлены offline regressions: различающиеся fingerprint и base URL отвергаются; существующие late-fill и conflicting-execId проверки сохранены.
- Fingerprint — устойчивый идентификатор credential scope, не доказательство личности владельца аккаунта или происхождения HTTP-ответа. При ротации API key сравнение старого и нового ключа fail-closed, даже если это один и тот же аккаунт.

Research CI #41918766426 — SUCCESS, 59/59 workflow steps; tested code commit `f552d42c30e57ec03e16db54eb2cf117730c2799`.

Ограничения:
- Snapshot schema v1/v2 нельзя использовать для межснимкового late-execution comparison: у них нет fingerprint.
- SHA-256 fingerprint не является server-authenticated account ID и не защищает от подделки самого snapshot; raw SHA-256 также остаётся локальной проверкой целостности.
- Никакие реальные API calls, credentials, collector runs, archive downloads, live orders или market PnL tests не выполнялись. CI использует offline fixtures/FakeTransport.
- Reconciliation PASS, live resume и strategy/execution/PnL gates остаются BLOCKED.

### ENG-RECON-020 — read-only dry-run план слияния поздних исполнений

Дата: 2026-11-05  
Статус: IMPLEMENTED / CI PENDING FINAL VERIFICATION.

Добавлена функция `build_execution_merge_plan(local_backup, snapshot)` в `scripts/bybit_reconciliation_report.py`.

Поведение:
- Принимает только schema v3 snapshot и backup с совпадающим `saved_at_utc`; parser повторно проверяет raw hash, page provenance, интервалы и typed exchange records.
- Строит план по symbol без изменения входного backup и без записи файлов.
- Требует exchange position identity для каждой затронутой локальной позиции.
- Проверяет, что каждый fill относится к известному локальному exchange order или entry order из position identity; проверяет symbol, side и orderLinkId.
- Точные повторные execId учитываются как duplicates; конфликтующая запись отклоняет весь расчёт до выдачи плана.
- Количества/цены сохраняются как Decimal text в `ExchangeExecutionIdentity`; план не применяет batch к engine state.
- Всегда возвращает `execution_history_complete=false`, `reconciliation_pass=false`, `live_resume_allowed=false`.

Offline tests: новая late fill proposal, exact duplicate и conflicting duplicate, orphan order rejection, отсутствие мутации backup.

CI: первоначальные прогоны выявили ошибки импорта и оформления тестового import statement; они исправлены. Итоговый CI для последнего SHA должен быть подтверждён отдельно.

Ограничения:
- Это только read-only proposal; нет команды apply, автоматической записи Plan B или вызова `merge_exchange_execution_batch`.
- Локальная позиция должна иметь точную exchange identity и локальные order records; legacy позиции без них fail closed.
- Проверка не доказывает полноту биржевой истории, не устраняет задержку API и не является разрешением на resume.
- Никакие Bybit API calls, collector runs, archive downloads, live orders или market PnL tests не выполнялись.
