# ENG-EXEC-002 — marketable limit entry fee classification

Статус: ACCEPT — классификация gap-through fills и регрессионные тесты прошли технический CI.  
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

Решение: ACCEPT для исследовательского движка.

- Исправление: commit `2a60a261ef5792b72d438ae39c5f99dda807c16e`.
- Тесты: commit `f1667c273d30c20306e59a746318c8be4d532172`.
- CI: [Research engine checks #41431923590](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41431923590), conclusion SUCCESS.
- `tests/test_gap_execution.py`: 25/25; оба marketable gap-through теста (long/short) и обычный non-gap limit-touch proxy отмечены PASS.
- `tests/test_time_model.py`: 38/38; регрессия ENG-KS-001 остаётся зелёной.
- Compile и все остальные deterministic checks прошли; secret scan не нашёл очевидных секретов.

Критерии выполнены. В marketable gap-through случаях effective entry type передаётся в sizing и сохраняется в позиции как `market`; обычный внутрисвечной limit touch остаётся `limit` proxy. Никакие рыночные backtests не запускались.

ACCEPT означает исправление классификации затрат в симуляторе. Он не доказывает, что остальные OHLC limit fills действительно получат maker execution.
