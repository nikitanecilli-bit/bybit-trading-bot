# Навигация по документации

## Читать в первую очередь

1. [Инструкции агенту](../AGENTS.md) — обязательные правила.
2. [Exchange reconciliation readiness](audits/EXCHANGE_RECONCILIATION_READINESS_RU.md) — read-only V5 snapshot contract и причина текущего BLOCKED.
3. [Рабочие правила проекта](../PROJECT_WORKING_RULES_RU.md) — автономность, безопасность и методика.
4. [Технический аудит](audits/PROJECT_AUDIT_RU.md).
5. [Аудит движка](audits/ENGINE_AUDIT_FINDINGS_RU.md).
6. [Журнал экспериментов](research/EXPERIMENT_LEDGER_RU.md) — исторический источник результатов.
7. [Протокол непрерывного улучшения](research/CONTINUOUS_IMPROVEMENT_PROTOCOL_RU.md) — гипотезы, контрольная версия, критерии ACCEPT/REJECT и защита от переобучения.
8. [Шаблон карточки эксперимента](research/EXPERIMENT_CARD_TEMPLATE_RU.md) — заполняется до каждого нового запуска.
9. [ENG-KS-001 — kill-switch priority](research/experiment_cards/ENG-KS-001_KILL_SWITCH_PRIORITY_RU.md) — исправление внутрисвечной конкуренции kill-switch и TP.
10. [ENG-EXEC-002 — marketable limit costs](research/experiment_cards/ENG-EXEC-002_MARKETABLE_LIMIT_FEE_RU.md) — taker-классификация лимитных gap-through fills.
11. [ENG-STATE-003 — fail-closed restore](research/experiment_cards/ENG-STATE-003_FAIL_CLOSED_RESTORE_RU.md) — не допускает тихой потери локального состояния при повреждённом backup.
12. [ENG-STATE-004 — fail-closed save](research/experiment_cards/ENG-STATE-004_FAIL_CLOSED_SAVE_RU.md) — останавливает цикл при неудачной записи резервного состояния.
13. [ENG-STATE-005 — transactional restore](research/experiment_cards/ENG-STATE-005_TRANSACTIONAL_RESTORE_RU.md) — не допускает частичного применения повреждённого backup.
14. [ENG-STATE-006 — pending schema](research/experiment_cards/ENG-STATE-006_PENDING_SCHEMA_RU.md) — проверяет содержимое восстановленных pending signals.
15. [ENG-STATE-007 — position schema](research/experiment_cards/ENG-STATE-007_POSITION_SCHEMA_RU.md) — проверяет типы, обязательные поля и инварианты восстановленных позиций.
16. [ENG-STATE-008 — TP1 invariants](research/experiment_cards/ENG-STATE-008_TP1_INVARIANTS_RU.md) — проверяет согласованность частичного закрытия TP1 и целей.
17. [ENG-STATE-009 — restore identity](research/experiment_cards/ENG-STATE-009_RESTORE_IDENTITY_RU.md) — исключает конфликт открытых позиций, pending и повторяющихся trade_id.
18. [ENG-STATE-010 — complete envelope](research/experiment_cards/ENG-STATE-010_COMPLETE_ENVELOPE_RU.md) — не допускает восстановления неполного JSON как пустого портфеля.
19. [ENG-STATE-011 — strict JSON save](research/experiment_cards/ENG-STATE-011_STRICT_JSON_SAVE_RU.md) — запрещает сохранение NaN/Infinity в резервной копии.
20. [ENG-STATE-018 — risk schema](research/experiment_cards/ENG-STATE-018_RISK_SCHEMA_RU.md) — проверяет числовые и логические поля восстановленного risk manager.
21. [ENG-STATE-012 — risk snapshot invariants](research/experiment_cards/ENG-STATE-012_RISK_SNAPSHOT_INVARIANTS_RU.md) — проверяет математическую согласованность equity и drawdown.
22. [ENG-STATE-013 — backup metadata](research/experiment_cards/ENG-STATE-013_BACKUP_METADATA_RU.md) — проверяет UTC timestamp и версию резервной копии.
23. [ENG-STATE-014 — TP1 timestamp](research/experiment_cards/ENG-STATE-014_TP1_TIMESTAMP_RU.md) — проверяет время события TP1 относительно входа.
24. [ENG-STATE-015 — pending next-bar chronology](research/experiment_cards/ENG-STATE-015_PENDING_NEXT_BAR_RU.md) — исключает исполнение устаревших pending-сигналов после пропуска свечи/перезапуска.
25. [ENG-STATE-016 — backup event chronology](research/experiment_cards/ENG-STATE-016_BACKUP_EVENT_TIME_RU.md) — запрещает событиям позиции/сигнала датироваться позже сохранения backup.
26. [ENG-STATE-017 — fsync backup durability](research/experiment_cards/ENG-STATE-017_FSYNC_BACKUP_RU.md) — fsync содержимого backup и каталога после atomic replace на POSIX.
27. [ENG-RECON-002 — read-only V5 parsers](research/experiment_cards/ENG-RECON-002_READONLY_PARSERS_RU.md) — strict parsing snapshots; no HTTP calls or account mutations.
28. [ENG-RECON-003 — read-only V5 collector](research/experiment_cards/ENG-RECON-003_READONLY_COLLECTOR_RU.md) — read-only capture implementation; mocked CI passed, no real Bybit snapshot captured.
29. [ENG-RECON-004 — report-only comparator](research/experiment_cards/ENG-RECON-004_REPORT_ONLY_COMPARATOR_RU.md) — validates snapshot integrity and reports differences; always blocks live resume.
30. [Матрица покрытия тестами](research/TEST_COVERAGE_MATRIX_RU.md).
31. [Следующий план исследований](research/NEXT_RESEARCH_PLAN_RU.md).
32. [Карта репозитория](REPOSITORY_MAP_RU.md).

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
