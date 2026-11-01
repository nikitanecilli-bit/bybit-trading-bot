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
Содержит 21 Python-скрипт и один markdown-файл с screening notes: сценарии E01–E09, диагностику режимов рынка, screening символов, holdout и вспомогательные проверки. Имена файлов сохраняются до проверки импортов и workflow references.

## .github/workflows/
Содержит 14 workflow: проверка данных Bybit, E09, execution ablation/walk-forward, gap/chase, H1 screening, portfolio validation, signal diagnostics, regime/market-structure holdout и общие research checks. Общий research-checks workflow объединяет технические проверки и рыночные расчёты; это отмечено как организационный риск.

## Правило будущей реорганизации
Переносить тесты в `tests/`, отчёты в `reports/`, данные в `data/` можно только отдельной серией атомарных коммитов после:
- проверки всех ссылок/путей;
- изменения workflow и импортов;
- добавления compatibility notes;
- проверки, что старые артефакты и ссылки остаются доступны.
До этого навигация выполняется через эту карту, а файлы остаются на местах.


## Межветочная карта полезных компонентов (2026-11-02)

| Ветка | Компоненты | Решение |
|---|---|---|
| `research/bybit-funding-data-v1` | Funding/mark downloader, funding PnL patch, CSV preparation adapter, funding regression tests | Сохранить; funding patch требует исправления mark-to-market accrued funding до переноса |
| `research/data-adapter-v1` | Bybit kline adapter, linear universe discovery, per-symbol backtest/report | Сохранить; сравнить с `prepare_backtest_data.py` и выбрать единый adapter |
| `research/v15-donchian-signal` | Независимый pure backtest, portfolio replay, TTL/stop/target/economics tests | Сохранить как cross-check; не заменять v14 без parity review |
| `research/market-regime-v1` | Более ранний regime + funding/data adapter слой | Сохранить как историческую исследовательскую ветку |
| `research/market-regime-v1-main` | Текущая документация, v14 audit, H1 regime/signal workflows, 50-symbol screening | Основная рабочая ветка |

## Текущие технические ограничения, важные для интерпретации результатов
- v14 использует notional approximation; биржевые `qtyStep`, `minOrderQty`, `minNotionalValue`, `tickSize`, margin tiers и liquidation пока не моделируются.
- Funding интеграция существует только в отдельной funding-ветке и имеет найденный пробел: accrued funding не входит в open mark-to-market equity.
- Mark/index/premium data downloader доступен, но в активном v14 engine эти потоки не используются для liquidation/basis modelling.
- Лимитные fills по OHLC касанию не моделируют очередь и partial fills.
- Последние четыре lifecycle regression tests добавлены в `test_gap_execution.py`; CI run для commit `c46178d624fa441ee2c5bd684beb42f5c5db3dbd` пока не подтверждён.

## Правило чистоты
Не перемещать/переименовывать `test_*.py`, `scripts/`, workflow, CSV и архивы до появления отдельного dependency inventory. Не удалять дублирующие адаптеры: сначала сравнить выходные схемы и тесты, затем выбрать canonical implementation отдельным коммитом.
