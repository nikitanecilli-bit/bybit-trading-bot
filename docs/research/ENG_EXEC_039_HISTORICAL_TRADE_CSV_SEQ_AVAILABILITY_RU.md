# ENG-EXEC-039 — Historical daily trade CSV: cross-sequence availability is unverified

Дата: 2026-11-04

## Вопрос

Содержит ли исторический файл `public.bybit.com/trading/<SYMBOL>/<SYMBOL><YYYY-MM-DD>.csv.gz` поле `seq`, которое Bybit публикует в live publicTrade и REST recent-trade?

## Что подтверждено

### 1. Официальный API contract

- Bybit V5 REST Get Recent Public Trades документирует поле `seq` как cross sequence. Официальный response example содержит `seq`.
- Bybit V5 WebSocket publicTrade также документирует `seq` как cross sequence.
- Orderbook stream документирует `seq` как cross sequence.
- REST docs говорят, что archived historical trades можно скачать с сайта Bybit, но не перечисляют CSV columns и не утверждают, что CSV сохраняет REST/WS `seq`.

Официальные ссылки:
- https://bybit-exchange.github.io/docs/v5/market/recent-trade
- https://bybit-exchange.github.io/docs/v5/websocket/public/trade
- https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook

### 2. Доступные описания historical CSV

Найденные внешние описания/реализации формата daily `public.bybit.com` CSV показывают header с полями:
`timestamp,symbol,side,size,price,tickDirection,trdMatchID,grossValue,homeNotional,foreignNotional`
(вариации дополнительных полей, включая RPI, зависят от версии/периода). В этих схемах `seq` не указан.

Это вторичные описания, а не официальная полная спецификация Bybit. Они дают основание считать отсутствие `seq` вероятным для распространённого CSV формата, но не доказывают его отсутствие во всех инструментах/датах/версиях архива.

### 3. Текущий репозиторий

- `iter_public_trades()` требует `timestamp,symbol,side,size,price,trdMatchID`, а также block-trade и RPI flag aliases.
- Парсер не запрещает неизвестные дополнительные колонки, но нормализованная trade запись не сохраняет `seq`.
- Существующие CSV fixtures в `tests/test_bybit_l2_queue_replay.py` используют headers без `seq`; это тестовые fixtures, не реальный sample архив.
- Следовательно, даже если реальный CSV содержит `seq`, текущий replay его отбрасывает. Если CSV не содержит `seq`, текущий исторический источник не даёт общего sequence tie-breaker.
- В репозитории нет проверенного сохранённого raw header из реального исторического daily CSV, который позволил бы закрыть этот вопрос без скачивания архива.

## Оценка

| Утверждение | Статус |
|---|---|
| Live WS publicTrade имеет `seq` | Подтверждено официальной документацией |
| REST recent-trade имеет `seq` | Подтверждено официальной документацией |
| Исторический daily CSV всегда имеет `seq` | Не подтверждено |
| Распространённая опубликованная CSV schema включает `seq` | Нет: в найденных схемах поле отсутствует |
| Текущий parser/replay использует trade `seq` | Нет |
| Межпоточный merge по `seq` сейчас обоснован | Нет |

## Решение

- Не менять parser и replay.
- Не делать вывод, что `seq` гарантированно отсутствует во всех исторических CSV: официальная schema не найдена.
- Для текущего historical CSV pipeline считать cross-stream sequence unavailable/unverified. Сохранять no-same-ms-fill и conservative timestamp policy.
- Если в будущем появится уже имеющийся легально сохранённый sample header (без нового скачивания) — проверить его происхождение, период, market/category и наличие `seq`. Если sample показывает поле, отдельно проверить полноту, тип, nulls, уникальность/монотонность и sequence domain относительно L2 прежде чем включать tie-break.
- Если подтверждённого sample нет, закрыть вопрос можно только отдельным одобренным data acquisition task; это не выполнять в рамках текущего статического аудита.

## Ограничения

- Статически прочитаны `bybit_l2_queue_replay.py`, тестовые fixtures, `scripts/run_bybit_l2_queue_replay.py`, а также публичные API docs и вторичные описания CSV schema.
- Реальные архивы, HEAD/GET/Range запросы к архивам, API endpoints и collectors не запускались.
- Тесты, queue replay, PnL/backtests, private API, runner и orders не запускались.
- Код/тесты не менялись. `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL`.
- `main` не изменён; PR #4 остаётся Draft/unmerged.
