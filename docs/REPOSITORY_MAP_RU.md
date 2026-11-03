# Карта репозитория

| Путь | Назначение |
|---|---|
| `.github/workflows/` | Технический CI и вручную запускаемые исследовательские workflow |
| `data/archives/cryptofetch/` | Неизменяемые исходные ZIP-архивы CryptoFetch |
| `dashboards/v15/` | Экспорт HTML/PDF дашборда v15 и инструкция |
| `dashboards/quant_analytics/` | Однофайловые версии v2.2/v2.3 и составные legacy HTML/JS части Quant Analytics; см. локальный README по версиям и ограничениям |
| `docs/audits/` | Аудиты кода и исследовательских ограничений |
| `docs/reports/` | Исторические backtest и диагностические отчёты |
| `docs/operations/` | Операционные инструкции и протоколы работы |
| `docs/research/` | Входные гипотезы, experiment queue, research plans и audit index |
| `research/legacy_tools/` | Архивные standalone-прототипы; не считать активными без проверки зависимостей; см. README с аудитом v16 |
| `scripts/` | Сбор данных, запуск анализа и технические утилиты |
| `tests/` | Регрессионные тесты |
| корень | README, пример env, исследовательский движок и downloader |

## Намеренно оставленные файлы в корне

- `Bybit_Trading_Engine_v14_research.py`: тесты и исследовательские скрипты импортируют его напрямую по корневому пути.
- `bybit_downloader.py`: публичный CLI, сохранён ради совместимости с README и привычными командами запуска.
- `.env.example`, `.gitignore`, `README.md`: стандартные корневые файлы репозитория.

## Последняя структурная уборка

- Корневые HTML-дашборды перемещены в `dashboards/quant_analytics/`; содержимое HTML не редактировалось.
- Когнитивный протокол перемещён в `docs/operations/`.
- `Fast Invariant Validator & 600-Token AI Digest Generator.py` перемещён в `research/legacy_tools/fast_invariant_validator_v16_legacy.py`. Он импортирует три отсутствующих legacy-модуля и потому заархивирован как неисполняемый прототип, а не включён в CI.
- Ни один Python-модуль, который импортируется активными tests/scripts/workflows, не перемещался. ZIP-архивы и исторические данные не изменялись.


## Исследовательские входы и Quant Lab

- Исходный список гипотез: [docs/research/hypothesis_inputs/Гипотезы_пользователя_2026-11-03.md](research/hypothesis_inputs/Гипотезы_пользователя_2026-11-03.md).
- Аудит загруженных Quant Lab/v16 материалов и приоритетная очередь: [QUANT_LAB_ASSETS_AND_HYPOTHESIS_QUEUE_2026-11-03_RU.md](research/QUANT_LAB_ASSETS_AND_HYPOTHESIS_QUEUE_2026-11-03_RU.md).
- v16 Python-прототипы остаются в legacy; Bridge заблокирован и не входит в active engine.
