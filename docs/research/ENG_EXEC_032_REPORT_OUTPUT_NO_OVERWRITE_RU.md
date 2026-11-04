# ENG-EXEC-032 — No-overwrite JSON report serialization

Дата: 2026-11-04

## Причина

Статический аудит трёх исследовательских скриптов выявил одинаковый риск: успешные отчёты записывались через `Path.write_text()` в фиксированные имена файлов без проверки существования. Повторный запуск в том же рабочем каталоге мог молча заменить предыдущий артефакт.

Затронутые выходы:
- `bybit_l2_queue_replay_report.json`;
- `bybit_trade_sample_inspection.json`;
- `bybit_orderbook_sample_inspection.json`.

## Исправление

- Добавлен общий `report_io.py` с `write_json_report(path, report)`.
- JSON сериализуется до открытия файла; сериализационная ошибка не создаёт файл.
- Файл открывается в exclusive-create режиме (`x`): существующий файл приводит к `FileExistsError`, исходные байты не меняются.
- Если запись уже созданного файла завершается ошибкой, неполный новый файл удаляется и ошибка пробрасывается вызывающему коду.
- Все три скрипта используют общий writer.
- Добавлены тесты на валидный JSON, отказ перезаписи без изменения исходных байтов и отсутствие файла при ошибке сериализации.

## Изменённые файлы и коммиты

- `report_io.py`: `0a58d10fd34674708623b48fee1a633ee3c8e5f3`.
- `scripts/run_bybit_l2_queue_replay.py`: `ddc3defd62a623f13bc4cb0db89392aab27b783e`, import correction `a70d75967867f609a0b1aa563591bb733a02911a`.
- `scripts/inspect_bybit_trade_sample.py`: `e2f484a7225baf3f4138ec7d3e9ad191161dba19`.
- `scripts/inspect_bybit_orderbook_sample.py`: `6bdedbebf9d29ca9381ebb08be35e03c9e65b736`.
- `tests/test_run_bybit_l2_queue_replay.py`: `ed089a1c9a6f0573a81357c4ee7116f709af1d53`.
- Branch: `research/market-regime-v1-main`; current verified HEAD at documentation time: `a70d75967867f609a0b1aa563591bb733a02911a`.

## CI и границы

- Изменения попадают под path filters `research-checks.yml` через изменённые runner/inspector/test paths. Workflow на push разрешён для этой research-ветки.
- Combined commit status пока не вернул check records; фактическое выполнение/успех CI для HEAD `a70d759` не подтверждены. Не заявлять тесты как выполненные.
- Не запускался workflow `bybit-orderbook-sample-inspection.yml`: он скачивает новые L2/trades archives и запускает bounded queue replay, что запрещено текущими gates.
- Исправление касается только сохранения диагностических JSON-артефактов. Это не execution evidence и не PnL.
- Не запускались collectors, новые архивы, private API, runner, рыночные PnL/backtests, paper/live orders.
- `MAKER_EXECUTION_REALISM = BLOCKED_FOR_STRATEGY_PNL` без изменений.
- `main` не изменялся; PR #4 не сливался.
