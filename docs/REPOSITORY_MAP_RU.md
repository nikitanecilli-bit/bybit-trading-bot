# Карта репозитория

## Корневые файлы
- `Bybit_Trading_Engine_v14_research.py` — движок симуляции.
- `bybit_downloader.py` — загрузчик.
- `PROJECT_WORKING_RULES_RU.md` — рабочие правила.
- `EXPERIMENT_LEDGER_RU.md` — журнал экспериментов.
- `REPORT_RU.md`, `HOLDOUT_REPORT_RU.md`, тематические отчёты — исторические выводы.
- `cryptofetch_*.zip` — наборы данных; immutable.
- `test_*.py` — регрессионные тесты в корне.

## scripts/
Содержит сценарии E01–E09, диагностику режимов рынка, screening символов, holdout и вспомогательные проверки. Имена файлов сохраняются до проверки импортов и workflow references.

## .github/workflows/
Содержит workflow для проверки данных Bybit, E09, execution ablation/walk-forward, gap/chase, H1 screening, portfolio validation, signal diagnostics и общие research checks.

## Правило будущей реорганизации
Переносить тесты в `tests/`, отчёты в `reports/`, данные в `data/` можно только отдельной серией атомарных коммитов после:
- проверки всех ссылок/путей;
- изменения workflow и импортов;
- добавления compatibility notes;
- проверки, что старые артефакты и ссылки остаются доступны.
До этого навигация выполняется через эту карту, а файлы остаются на местах.
