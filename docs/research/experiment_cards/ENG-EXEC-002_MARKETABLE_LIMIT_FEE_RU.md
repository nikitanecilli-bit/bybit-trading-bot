# ENG-EXEC-002 — marketable limit entry fee classification

Статус до исправления: HYPOTHESIS REGISTERED / ошибка подтверждена чтением кода.  
Дата: 2026-11-02.  
Тип: deterministic execution-cost accounting regression; не рыночный эксперимент.

## Наблюдаемая проблема

В `UnifiedQuantEngine._try_fill_pending()` limit order, который открывается гэпом через лимитную цену, исполняется по более выгодному `curr.open`. Однако движок передаёт `order_type="limit"` в sizing и сохраняет его в позиции. Далее `_unrealized_pnl_at_marks()` и `_close_position()` трактуют любую такую позицию как maker entry: maker fee и нулевой entry slippage.

Для buy limit с `open < limit` и sell limit с `open > limit` заявка на открытии marketable: исполнение забирает ликвидность, а не добавляет её. Следовательно, maker fee для таких gap-through fills — оптимистичная классификация.

## Предварительная гипотеза

Классифицировать marketable limit gap-through на открытии как taker:
- long: если `curr.open < ref`, entry liquidity = taker;
- short: если `curr.open > ref`, entry liquidity = taker;
- если гэпа через лимит нет и лимит касается позже в свече, сохранить текущую maker-proxy классификацию, явно признавая, что OHLC не доказывает maker fill.

Эффективный тип входа должен использоваться и для оценки риска/размера, и для последующего расчёта entry fees/slippage в журнале. Отдельная настройка maker exits сохраняется: классификация входа не должна молча менять тип TP/exit.

## Критерии проверки

- Buy limit gap-through и sell limit gap-through классифицируются как taker.
- В sizing передаётся taker, а сохранённая позиция/журнал отражает taker entry.
- Обычный limit touch без gap-through остаётся maker proxy.
- Существующие gap, fee-leg, stop/TP, kill-switch и portfolio tests остаются зелёными.
- Никаких рыночных backtests, параметрических оптимизаций или изменений production/live.

## Риски и границы

- Даже non-gap OHLC touch не гарантирует maker fill: нет bid/ask, queue priority, partial fills и adverse selection.
- Taker slippage constant остаётся proxy; это не модель фактического исполнения.
- Исправление делает gap-through accounting менее оптимистичным, но не делает весь execution model реалистичным.

## Решение

OPEN до regression tests и CI. ACCEPT только при выполнении критериев; иначе REJECT/INCONCLUSIVE с логами.
