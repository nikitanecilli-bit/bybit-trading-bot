# Аудит много-свечного ожидания лимитных заявок — 2026-11-04

Ветка: `research/market-regime-v1-main`  
Проверенный execution code + CI configuration commit: `f1bc3ffc140dfa288c0ec575c2a1f3c163cf2a1f`  
Research CI: [#41808762750 — SUCCESS, 55/55 steps](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41808762750)  
Документационные уточнения после проверки: `8f844f41e6f5cefed89813159b1e0f3679032b66`

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
- `scripts/run_h1_limit_fill_stress.py`

Перед каждой повторной попыткой лимитной заявки runner теперь вызывает `prepare_signal_for_next_bar_fill()`: временной guard обновляется для текущей свечи, а исходный timestamp сохраняется в `signal_origin_ts` для provenance.

`run_h1_shared_capital_portfolio_validation.py` уже использует этот адаптер. `run_h1_limit_fill_stress.py` теперь использует общий `evaluate_limit_wait()` с `open_price`: гэп через лимит становится немедленным fill, а повторные попытки проходят через тот же freshness adapter.

## Регрессионная защита и CI

- Добавлен тест последовательных попыток на нескольких свечах: guard меняется, `signal_origin_ts` остаётся неизменным.
- В Research CI добавлена компиляция всех исправленных runners.
- В CI path filters добавлены эти файлы, чтобы их изменения запускали проверку.
- Commit `f1bc3ff`: compile step включает все 13 исправленных runners; multi-bar lifecycle tests и полный Research CI завершились SUCCESS (55/55 steps).

## Влияние на прежние результаты

Любые результаты с `wait_bars > 1`, полученные перечисленными runners до исправления, нельзя трактовать как честное сравнение TTL, если соответствующий запуск действительно использовал limit mode: фактическое ожидание могло завершаться на первой свече из-за stale guard. Это относится к механике эксперимента, а не доказывает, что PnL был завышен или занижен.

В `run_h1_limit_fill_stress.py` дополнительно устранена отдельная ошибка: старая ветка не распознавала marketable open gap и применяла только intrabar penetration. Теперь используется общий классификатор с ценой открытия. В этом аудите старые результаты не пересчитывались, рыночный PnL replay не запускался. Перед повторным использованием нужно проверить наличие исторических workflow artifacts и перезапустить только действительно нужные эксперименты на корректной механике.

## Дополнительные runners с реальным multi-bar limit path (2026-11-04)

После расширения аудита исправлены ещё четыре runner:
- `scripts/run_e09_h1_gate_factorial.py` — реально перебирает `market` и `limit`, поэтому limit-ветка E09 была затронута;
- `scripts/run_e10_h1_body_gate_replication.py` — текущий main запускает только market mode; limit-ветка исправлена на будущее;
- `scripts/run_h1_signal_quality_ablation.py` — фиксированное 3-bar limit ожидание, исправлены как fill-, так и no-touch вызовы движка;
- `scripts/run_h1_signal_trade_diagnostics.py` — 3-bar limit execution для диагностики сделок.

В E09/E10 и H1 diagnostics временной guard обновляется непосредственно перед каждой попыткой вызова движка. В signal-quality runner обновление выполняется также перед искусственным no-touch вызовом, чтобы движок корректно потреблял текущую свечу и не удалял сигнал как stale.

Дополнительно E11/E13 optional limit paths исправлены ранее. Их исторические workflow #41361376448 и #41362217727 были market-only, поэтому их архивный PnL не затронут.

Добавлен end-to-end regression `test_engine_accepts_limit_fill_on_third_wait_bar_and_preserves_origin_signal_ts`: два no-touch бара, fill на третьем, original signal timestamp сохранён. Все исправленные runners добавлены в compile step и CI path filters.

## Ограничения, не устранённые этим исправлением

- OHLC touch/penetration не подтверждает реальное исполнение в очереди.
- Не моделируются bid/ask spread, L2 queue priority, partial fills, cancel latency и adverse selection.
- Поэтому maker fills остаются оптимистичной верхней границей, а не доказанным исполнением Bybit.
- Никакие реальные ордера не размещались.


## Дополнительная проверка E11/E13 runners (2026-11-04)

Статический аудит обнаружил ту же потенциальную проблему в optional limit-execution ветках:
- `scripts/run_e11_h1_shared_capital_replay.py`
- `scripts/run_e13_h1_compression_gate_replay.py`

В обеих ветках `execution_mode="limit"` повторные попытки теперь обновляют freshness guard через `prepare_signal_for_next_bar_fill()`, сохраняя исходный timestamp сигнала. Эти два runner добавлены в Research CI compile step и path filters.

**Важная оговорка по историческим результатам:** проверены workflow-файлы и точки вызова `run_fold()`. Исторические E11 run [#41361376448](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41361376448) и E13 run [#41362217727](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41362217727) запускали `execution_mode="market"`. Поэтому их опубликованные market-mode результаты не затрагиваются этим дефектом. Проблема относилась к поддерживаемой в коде limit-mode ветке, но не к конфигурации этих двух архивных прогонов. Не объявлять E11/E13 PnL недействительным по этой причине.
