# Аудит много-свечного ожидания лимитных заявок — 2026-11-04

Ветка: `research/market-regime-v1-main`  
Проверенный commit: `ad9fdc79e2b5ccfe633bc4cd1adccb4dfd4a7418`  
Research CI: [#41807674494 — SUCCESS](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41807674494)

## Подтверждённая причина

Базовый `UnifiedQuantEngine._try_fill_pending()` намеренно принимает сигнал только на следующей свече: проверяет `signal_ts + timeframe_ms == candle.ts`. Это корректная защита от устаревших сигналов для обычного next-bar execution.

Исследовательские обвязки с много-свечным ожиданием повторно вызывали этот метод на последующих свечах, но сохраняли исходный `signal_ts`. Поэтому со второй свечи движок удалял заявку как stale, и заданные TTL 3/5 баров фактически не работали.

## Исправленные runners

- `scripts/run_execution_cost_ablation.py`
- `scripts/run_execution_walk_forward.py`
- `scripts/run_h1_long_execution_sensitivity.py`
- `scripts/run_h1_direction_execution_ablation.py`
- `scripts/run_h1_chase_limit_ablation.py`
- `scripts/run_h1_chase_gate_decoupling.py`

Перед каждой повторной попыткой лимитной заявки runner теперь вызывает `prepare_signal_for_next_bar_fill()`: временной guard обновляется для текущей свечи, а исходный timestamp сохраняется в `signal_origin_ts` для provenance.

`run_h1_shared_capital_portfolio_validation.py` уже использует этот адаптер. `run_h1_limit_fill_stress.py` также имеет отдельную реализацию с сохранением исходного timestamp.

## Регрессионная защита и CI

- Добавлен тест последовательных попыток на нескольких свечах: guard меняется, `signal_origin_ts` остаётся неизменным.
- В Research CI добавлена компиляция всех шести исправленных runners.
- В CI path filters добавлены эти файлы, чтобы их изменения запускали проверку.
- Commit `ad9fdc7`: compile step, multi-bar lifecycle tests и полный Research CI завершились SUCCESS.

## Влияние на прежние результаты

Любые результаты с `wait_bars > 1`, полученные шестью перечисленными runners до исправления, нельзя трактовать как честное сравнение TTL: фактическое ожидание могло завершаться на первой свече из-за stale guard. Это относится к механике эксперимента, а не доказывает, что PnL был завышен или занижен.

В этом аудите старые результаты не пересчитывались, рыночный PnL replay не запускался. Перед повторным использованием нужно проверить наличие исторических workflow artifacts и перезапустить только действительно нужные эксперименты на корректной механике.

## Ограничения, не устранённые этим исправлением

- OHLC touch/penetration не подтверждает реальное исполнение в очереди.
- Не моделируются bid/ask spread, L2 queue priority, partial fills, cancel latency и adverse selection.
- Поэтому maker fills остаются оптимистичной верхней границей, а не доказанным исполнением Bybit.
- Никакие реальные ордера не размещались.
