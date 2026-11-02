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
3. **Executions:** `GET /v5/execution/list?category=linear&startTime=...&endTime=...&limit=100`, пройти все страницы. Сохранить `execId`, `orderId`, `orderLinkId`, `symbol`, `side`, `execQty`, `execPrice`, `execTime`, `execType`, `execFee`. Один ордер может иметь несколько execution rows; дедупликация должна быть по execution identity, не по orderId.
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

- **ENG-RECON-002 ACCEPT:** `bybit_reconciliation.py` добавлен как pure parser для paginated V5 positions, active orders и executions. 12/12 fixture tests passed; CI #41448536690 SUCCESS.
- Парсер не делает HTTP calls, не использует ключи и не отправляет ордера. Он проверяет только переданные ему страницы; он не доказывает, что вызывающий код получил все страницы.
- Следующий слой: read-only collector with cursor loop + server-time coherence, затем report-only comparator.
- Общий статус по-прежнему `UNSUPPORTED_LOCAL_MODEL / BLOCKED`: exact local qty, `positionIdx`, order IDs/link IDs и execution ledger отсутствуют.
