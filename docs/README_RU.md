# Навигация по документации

## Читать в первую очередь

1. [Инструкции агенту](../AGENTS.md) — обязательные правила.
2. [Рабочие правила проекта](../PROJECT_WORKING_RULES_RU.md) — автономность, безопасность и методика.
3. [Технический аудит](audits/PROJECT_AUDIT_RU.md).
4. [Аудит движка](audits/ENGINE_AUDIT_FINDINGS_RU.md).
5. [Журнал экспериментов](research/EXPERIMENT_LEDGER_RU.md) — исторический источник результатов.
6. [Протокол непрерывного улучшения](research/CONTINUOUS_IMPROVEMENT_PROTOCOL_RU.md) — гипотезы, контрольная версия, критерии ACCEPT/REJECT и защита от переобучения.
7. [Шаблон карточки эксперимента](research/EXPERIMENT_CARD_TEMPLATE_RU.md) — заполняется до каждого нового запуска.
8. [ENG-KS-001 — kill-switch priority](research/experiment_cards/ENG-KS-001_KILL_SWITCH_PRIORITY_RU.md) — исправление внутрисвечной конкуренции kill-switch и TP.
9. [ENG-EXEC-002 — marketable limit costs](research/experiment_cards/ENG-EXEC-002_MARKETABLE_LIMIT_FEE_RU.md) — taker-классификация лимитных gap-through fills.
10. [ENG-STATE-003 — fail-closed restore](research/experiment_cards/ENG-STATE-003_FAIL_CLOSED_RESTORE_RU.md) — не допускает тихой потери локального состояния при повреждённом backup.
11. [ENG-STATE-004 — fail-closed save](research/experiment_cards/ENG-STATE-004_FAIL_CLOSED_SAVE_RU.md) — останавливает цикл при неудачной записи резервного состояния.
12. [ENG-STATE-005 — transactional restore](research/experiment_cards/ENG-STATE-005_TRANSACTIONAL_RESTORE_RU.md) — не допускает частичного применения повреждённого backup.
13. [ENG-STATE-006 — pending schema](research/experiment_cards/ENG-STATE-006_PENDING_SCHEMA_RU.md) — проверяет содержимое восстановленных pending signals.
14. [ENG-STATE-007 — position schema](research/experiment_cards/ENG-STATE-007_POSITION_SCHEMA_RU.md) — проверяет типы, обязательные поля и инварианты восстановленных позиций.
15. [ENG-STATE-008 — TP1 invariants](research/experiment_cards/ENG-STATE-008_TP1_INVARIANTS_RU.md) — проверяет согласованность частичного закрытия TP1 и целей.
16. [ENG-STATE-009 — restore identity](research/experiment_cards/ENG-STATE-009_RESTORE_IDENTITY_RU.md) — исключает конфликт открытых позиций, pending и повторяющихся trade_id.
17. [ENG-STATE-010 — complete envelope](research/experiment_cards/ENG-STATE-010_COMPLETE_ENVELOPE_RU.md) — не допускает восстановления неполного JSON как пустого портфеля.
18. [ENG-STATE-011 — strict JSON save](research/experiment_cards/ENG-STATE-011_STRICT_JSON_SAVE_RU.md) — запрещает сохранение NaN/Infinity в резервной копии.
19. [ENG-STATE-008 — risk schema](research/experiment_cards/ENG-STATE-008_RISK_SCHEMA_RU.md) — проверяет числовые и логические поля восстановленного risk manager.
20. [ENG-STATE-012 — risk snapshot invariants](research/experiment_cards/ENG-STATE-012_RISK_SNAPSHOT_INVARIANTS_RU.md) — проверяет математическую согласованность equity и drawdown.
21. [Матрица покрытия тестами](research/TEST_COVERAGE_MATRIX_RU.md).
22. [Следующий план исследований](research/NEXT_RESEARCH_PLAN_RU.md).
23. [Карта репозитория](REPOSITORY_MAP_RU.md).

## Разделы

- `audits/` — технические аудиты, сравнение веток и подтверждённые ограничения.
- `reports/` — исторические backtest, holdout и диагностические отчёты.
- `research/` — журнал экспериментов, протокол исследований, шаблоны, матрица тестового покрытия и исследовательский план.

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
