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
