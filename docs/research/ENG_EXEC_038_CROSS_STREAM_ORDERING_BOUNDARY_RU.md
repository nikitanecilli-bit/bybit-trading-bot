# ENG-EXEC-038 — Cross-stream ordering boundary for L2 and public trades

Дата: 2026-11-04

## Вопрос аудита

Можно ли объединить текущие архивы order book и public trades в одну временную ленту так, чтобы достоверно определить, предшествовала ли сделка изменению уровня книги (и наоборот)?

## Подтверждённые факты

### Контракт Bybit

Официальная документация Bybit указывает:

- В order-book stream поле `cts` — matching-engine timestamp создания book update; документация прямо говорит, что его можно коррелировать с `T` из public trade channel.
- В publicTrade stream `T` — время исполнения сделки; элементы выдаются в порядке времени сделки. Для сделки также публикуется `seq` (cross sequence).
- В order-book stream есть `seq` (cross sequence); документация описывает его как средство сравнения порядка событий, где меньшее значение создано раньше.
- REST Get Recent Public Trades также возвращает `seq`.

Ссылки:
- https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook
- https://bybit-exchange.github.io/docs/v5/websocket/public/trade
- https://bybit-exchange.github.io/docs/v5/market/recent-trade
- https://bybit-exchange.github.io/docs/v5/market/orderbook

### Текущий архивный pipeline в репозитории

- Queue runner скачивает L2 ZIP из `quote-saver.bycsi.com/orderbook/linear` и daily trades CSV.GZ из `public.bybit.com/trading`.
- `iter_book_events()` сохраняет `cts`, `seq` и `u` в order-book events.
- `iter_public_trades()` нормализует timestamp, side, price, size, trade ID, RPI и block-trade flags, но не извлекает и не передаёт trade `seq` в replay. Если исходный CSV содержит дополнительные колонки, текущая нормализация всё равно их отбрасывает.
- `replay_public_trades()` валидирует порядок trade timestamps внутри trade archive отдельно. `capture_book_at()` валидирует порядок L2 timestamps/seq внутри book archive отдельно. Эти проверки не создают межпоточный порядок.
- Runner намеренно не применяет L2 events с `cts == arrival` до снимка заявки и явно декларирует `no same-ms fills`. Markout snapshot также исключает book events той же миллисекунды, поскольку порядок относительно гипотетического события не установлен.

## Вывод

1. Разные миллисекундные timestamps дают консервативный временной порядок при условии корректной семантики исходных часов: меньший engine timestamp раньше большего. Bybit описывает `cts` и `T` как коррелируемые matching-engine timestamps.
2. Равные миллисекундные timestamps не задают порядок внутри одной миллисекунды. По одному timestamp нельзя решить, была ли сделка до или после конкретного L2 update.
3. Bybit публикует cross-sequence `seq` и в publicTrade, и в orderbook. Это потенциальный tie-breaker/общая ось порядка. Но текущий daily CSV adapter не передаёт trade `seq`, поэтому использовать его в текущем replay невозможно.
4. Наличие `seq` в REST recent-trade не доказывает, что оно доступно в историческом daily CSV за весь требуемый период. Это нужно подтвердить на документации/реальном образце соответствующего архива, прежде чем менять контракт parser.
5. Даже общий порядок событий сам по себе не решает maker queue allocation: он только устраняет часть временной неоднозначности. L2 aggregate всё равно не раскрывает, какая доля сокращения объёма была отменой впереди/позади нашей заявки.

## Решение

- Не объединять потоки по произвольному tie-breaker (например, всегда trade-first или book-first).
- Сохранить текущую консервативную политику: не кредитовать same-ms fills; не применять same-ms book events для pre-arrival/markout snapshot.
- Не менять код до подтверждения наличия и семантики trade `seq` в используемых исторических CSV.
- Следующий допустимый шаг — исследовать контракт исторического daily CSV (без скачивания архива): найти авторитетное описание schema либо использовать уже имеющийся в репозитории образец/fixture. Если trade `seq` в этом формате отсутствует, cross-stream tie resolution остаётся недоступным для этих архивов.
- Даже при наличии `seq` потребуется отдельная проверка монотонности/уникальности и соответствия sequence domains до реализации merge.

## Проверки и ограничения

- Статически прочитаны queue replay core, tests, runner, trade inspector и ENG-EXEC-031.
- Проверены официальные страницы Bybit API docs; никакие API-запросы и архивы не скачивались.
- Код/тесты не менялись; тесты, queue replay, PnL/backtests, collectors, network workflows, private API, runner и paper/live orders не запускались.
- `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` без изменений.
- `main` не изменён; PR #4 остаётся Draft/unmerged.
