# Навигация по документации

## Читать в первую очередь

1. [Инструкции агенту](../AGENTS.md) — обязательные правила.
2. [Рабочие правила проекта](../PROJECT_WORKING_RULES_RU.md) — автономность, безопасность и методика.
3. [Технический аудит](audits/PROJECT_AUDIT_RU.md).
4. [Аудит движка](audits/ENGINE_AUDIT_FINDINGS_RU.md).
5. [Журнал экспериментов](research/EXPERIMENT_LEDGER_RU.md) — исторический источник результатов.
6. [Матрица покрытия тестами](research/TEST_COVERAGE_MATRIX_RU.md).
7. [Следующий план исследований](research/NEXT_RESEARCH_PLAN_RU.md).
8. [Карта репозитория](REPOSITORY_MAP_RU.md).

## Разделы

- `audits/` — технические аудиты, сравнение веток и подтверждённые ограничения.
- `reports/` — исторические backtest, holdout и диагностические отчёты.
- `research/` — журнал экспериментов, матрица тестового покрытия и исследовательский план.


## Последние исследовательские результаты

- [E09 — различия трёх периодов](reports/E09_FOLD_DIFFERENCES_RU.md): body gate и рыночный фон.
- [E10 — cross-sectional body gate, 47 инструментов](reports/E10_H1_BODY_GATE_CROSS_SECTIONAL_RU.md): per-symbol независимые прогоны.
- [E11 — shared-capital портфель, 47 инструментов](reports/E11_H1_SHARED_CAPITAL_PORTFOLIO_RU.md): единый капитал и конкуренция за позиции.
- [E12 — broad-market context diagnostics](reports/E12_BROAD_MARKET_CONTEXT_DIAGNOSTICS_RU.md): breadth, momentum, ATR и cross-sectional dispersion.
- [E13 — causal compression gate](reports/E13_CAUSAL_COMPRESSION_GATE_RU.md): один фиксированный фильтр на shared capital.


## Технические блокеры перед execution-aware replay

- [Execution realism readiness audit](audits/EXECUTION_REALISM_READINESS_RU.md): отсутствие Bybit snapshot на GitHub runner, неподключённый exchange sizing, funding/mark proxy и ограничения модели издержек.

## Методологические правила

- CI подтверждает только выполнение перечисленных технических проверок.
- Market backtest, walk-forward и ablation запускаются только вручную через отдельные workflow.
- Binance OHLCV — proxy для Bybit, не доказательство реального исполнения.
- Независимые per-symbol PnL нельзя трактовать как shared-capital portfolio result.
- Сохранять отрицательные результаты, исходные архивы и holdout без перезаписи.
