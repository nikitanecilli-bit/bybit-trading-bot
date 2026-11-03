# Runbook: накопление официальных Bybit execution snapshots и market history

## 1. Ограничение источников

Публичные V5 endpoints instruments-info и risk-limit возвращают текущие параметры, а не исторические версии на произвольный timestamp. Поэтому восстановить точные прошлые qtyStep/minNotional/maxQty/risk tiers задним числом этим API нельзя. История начинается с момента первого успешно сохранённого снимка.

Источники:
- https://bybit-exchange.github.io/docs/v5/market/instrument
- https://bybit-exchange.github.io/docs/v5/market/risk-limit
- https://bybit-exchange.github.io/docs/v5/market/funding/history
- https://bybit-exchange.github.io/docs/v5/market/mark-price-kline
- https://bybit-exchange.github.io/docs/v5/market/kline

## 2. Runner

GitHub-hosted runner в США уже дал HTTP 403 от Bybit. Для загрузки данных нужен GitHub self-hosted runner с label self-hosted и исходящим IP вне США и материкового Китая.

В репозитории: Settings → Actions → Runners → New self-hosted runner. Установить runner на постоянно доступном компьютере/VPS в разрешённом регионе и выполнить выданные GitHub команды. Не добавлять API keys: перечисленные market-data endpoints публичные.

**Статус публикации collector workflow (обновлено 2026-11-03):** три collector workflow выборочно опубликованы в default branch `main` через PR #8 (`a0ceb66d9b2cf818b3a24d723130d1125c8ca382`). Они явно checkout-ят `research/market-regime-v1-main`, запускают код из этой ветки и сохраняют архивы обратно туда. H1 validation workflow в `main` пока отсутствует. PR #4 целиком для этого не использовать: он сильно diverged.

Если аккаунт зарегистрирован на казахстанском сайте Bybit, задать repository variable BYBIT_API_BASE_URL=https://api.bybit.kz; в любом случае hostname должен соответствовать сайту регистрации аккаунта.

## 3. Сбор

1. Collector workflow теперь доступны в GitHub Actions из `main`: запустить Archive Bybit instrument specifications с runner=self-hosted. Текущий YAML содержит только `workflow_dispatch`; расписание не настроено.
2. Запустить Archive Bybit risk-limit tiers с runner=self-hosted. Текущий YAML содержит только `workflow_dispatch`; расписание не настроено.
3. Запустить Archive Bybit OHLCV, funding and mark-price history с runner=self-hosted. Указать symbols, start_ms и end_ms (end exclusive, границы H1), interval=60. Результат сохраняется в data/archives/bybit/<start_ms>_<end_ms>_<run_id>/{kline,funding,mark_price}. Текущий YAML также только ручной, без cron.

## 4. Запуск H1 validation

Workflow H1 Shared-Capital Portfolio Validation принимает три repository-relative каталога:
- kline_dir — Bybit H1 trade candles;
- funding_dir — funding settlement CSV;
- mark_price_dir — mark-price H1 candles.

Дополнительный необязательный input `symbols` принимает замороженный список через запятую (например, `BTCUSDT,ETHUSDT,SOLUSDT`). Если поле пустое, применяется coverage-based universe selection. Для заранее выбранной группы top-5 + reserve-5 указывать все 10 символов явно, чтобы разные прогоны не выбирали universe заново.

Для одной полной архивной сессии это каталоги kline, funding и mark_price внутри одного archive root. При нескольких архивных сессиях CSV нужно предварительно объединить по символу без потери/конфликта timestamps; не складывать одноимённые файлы поверх друг друга.

Workflow публикует два артефакта: итоговый `h1_shared_capital_portfolio_validation.csv` и `h1_shared_capital_portfolio_validation_manifest.json`. Manifest содержит выбранные символы, общий H1 timestamp grid, точные fold boundaries, параметры стратегии/risk/execution, SHA-256 и размеры входных CSV/JSON, hashes ключевых code/workflow files, Git commit и workflow run metadata, а также hash выходного CSV. Хеши фиксируют точные байты файлов, но сами по себе не удостоверяют удалённое происхождение данных — origin по-прежнему должен подтверждаться collector workflow и путями архивов.

## 5. Обязательное временное покрытие

Каждый scored fold должен иметь:
- instrument snapshot и risk-tier snapshot не позднее начала fold;
- возраст первого применимого снимка не более 30 дней;
- интервалы между снимками не более 30 дней;
- возраст последнего применимого снимка на конец fold не более 30 дней;
- funding events и mark-price candles на всех требуемых timestamps;
- Bybit trade-kline и mark-kline с одинаковой временной сеткой.

Текущий снимок не может подтвердить исторические свечи, предшествующие этому снимку. Не копировать сегодняшние параметры назад во времени и не отключать fail-closed gate ради получения PnL.

## 6. Ограничения после сбора

Даже при полном покрытии данных остаются приближениями: OHLC penetration вместо реальной очереди лимитной заявки, отсутствие исторического bid/ask spread и partial-fill adverse selection, mark-candle open как proxy funding settlement mark, базовые maker/taker fee rates вместо персонального fee tier, отсутствие account-mode-specific liquidation model. Эти ограничения должны быть отражены в отчёте каждого теста.


## 7. Что требуется до первого запуска

- [ ] Выборочно перенести collector workflows и их Python-модули/зависимости в отдельную ветку от актуального `main`; не переносить весь PR #4.
- [x] Добавить три collector workflow в default branch (PR #8, merge commit `a0ceb66d9b2cf818b3a24d723130d1125c8ca382`). H1 validation workflow остаётся только в research branch.
- [ ] Отдельно решить и реализовать расписание snapshots после успешного первого ручного сбора; сейчас `schedule`/cron отсутствует.
- [ ] Проверить, что self-hosted runner зарегистрирован и имеет label `self-hosted`, а egress country не US/CN. Доступных через текущую GitHub-интеграцию сведений о registered runners нет, поэтому этот пункт пока UNVERIFIED.
- [ ] Запустить сначала snapshots, затем ограниченный архив H1 и проверить coverage/artifacts до любого PnL.
