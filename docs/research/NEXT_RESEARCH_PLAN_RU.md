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
3. Запустить Archive Bybit linear universe history с runner=self-hosted и дождаться коммита snapshot в research branch. Выбрать конкретный файл `data/universe_history/linear/<UTC timestamp>.json` из ветки.
4. Запустить Archive Bybit OHLCV, funding and mark-price history с runner=self-hosted. Указать symbols, start_ms, end_ms (end exclusive, H1-aligned), interval=60 и точный repository-relative путь к universe_snapshot. Collector требует, чтобы каждый символ присутствовал в snapshot как USDT LinearPerpetual; символы вне snapshot не архивируются.
5. Для каждого символа диапазон автоматически обрезается по launchTime/deliveryTime. Первый бар округляется вверх до первого полного H1 open не раньше launchTime; end-exclusive округляется вниз по deliveryTime, чтобы не включать бар, пересекающий delivery. Если после clipping нет ни одного полного бара, весь запуск прекращается до сетевых запросов. В archive_manifest записываются исходный и фактический диапазоны, lifecycle/status, snapshot fetched_at и SHA-256.
Результат сохраняется в data/archives/bybit/<start_ms>_<end_ms>_<run_id>/{kline,funding,mark_price}. Workflow остаётся manual-only, без cron.

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

- [x] Выборочно опубликовать три collector workflow из актуального `main` (PR #8, merge commit `a0ceb66d9b2cf818b3a24d723130d1125c8ca382`). Они намеренно checkout-ят `research/market-regime-v1-main`, где остаются Python-модули и зависимости; переносить весь PR #4 нельзя.
- [x] Добавить три collector workflow в default branch. H1 validation workflow остаётся только в research branch.
- [ ] Отдельно решить и реализовать расписание snapshots после успешного первого ручного сбора; сейчас `schedule`/cron отсутствует.
- [ ] Проверить, что self-hosted runner зарегистрирован и имеет label `self-hosted`, а egress country не US/CN. Доступных через текущую GitHub-интеграцию сведений о registered runners нет, поэтому этот пункт пока UNVERIFIED.
- [ ] Запустить сначала snapshots, затем ограниченный архив H1 и проверить coverage/artifacts до любого PnL.


## 9. Per-symbol lifecycle clipping (2026-11-03)

- Архиватор больше не использует один и тот же сырой интервал для всех символов без проверки жизненного цикла.
- Для каждого запрошенного тикера обязателен конкретный Bybit linear universe snapshot из repository checkout. Входной файл проверяется по структуре и SHA-256 включается в archive manifest.
- Границы считаются консервативно на уровне полных свечей: `effective_start = max(requested_start, ceil(launchTime / interval) * interval)`; `effective_end = min(requested_end, floor(deliveryTime / interval) * interval)`, если deliveryTime задан. Для бессрочного контракта deliveryTime=0, верхней границей остаётся requested_end.
- Если тикер отсутствует в snapshot или пересечение не содержит полного бара, сбор прекращается до начала сетевых запросов. Это намеренный fail-closed подход.
- Snapshot отражает только зафиксированный состав и lifecycle Bybit на момент сбора. Он не доказывает полноту исторического universe, не восстанавливает временные приостановки торгов и не гарантирует, что Bybit сохраняет все делистнутые контракты в endpoint. Неизвестный/отсутствующий инструмент не должен молча считаться «не торговался».
- Workflow в `main` и соответствующий workflow в research branch синхронизированы по обязательному input `universe_snapshot`; исполняемый Python collector остаётся в research branch, которую workflow checkout-ит явно.

## 8. Статическая перепроверка 2026-11-03

- Collector YAML в `main` существует и остаётся manual-only. В доступной GitHub-интеграции этой сессии нет операции `workflow_dispatch` и нет чтения списка зарегистрированных self-hosted runners; поэтому фактический запуск и runner availability не подтверждены.
- Archive downloader запрашивает Bybit V5 trade klines, funding history и mark-price klines, использует end-exclusive UTC диапазон, проверяет alignment/полноту H1 grid, режет запросы на bounded windows и атомарно пишет CSV. Funding pagination рекурсивно делит насыщенные 200-row windows.
- Coverage gate проверяет наличие funding событий, mark candles на каждом funding timestamp и полное совпадение timestamp sets trade/mark H1. Это необходимая проверка целостности, но не проверка корректности самих рыночных цен/ставок и не доказательство exchange fills.
- Instrument/risk-limit snapshots являются point-in-time наблюдениями; они не восстанавливают исторические параметры до первого сохранённого снимка.
- Никаких новых PnL запусков не выполнялось: Bybit archive и датированные snapshots пока отсутствуют. Следующий реальный эксперимент не запускать до появления этих данных.


**Детерминированные collector tests:** Research CI [#41689536499 — SUCCESS](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41689536499) выполнен на исследовательской ветке; все шаги успешны, включая instrument snapshot collector, risk-limit snapshot collector, market-history archive collector и funding/mark coverage preflight. Это offline/mock tests, не сетевой сбор реальных Bybit данных.


## 2026-11-03 — per-symbol lifecycle-aware Bybit archive

- `scripts/archive_bybit_market_history.py` теперь требует конкретный dated Bybit linear universe snapshot. Файл должен быть внутри checkout, иметь категорию linear, fetched_at и непустой instruments[]; SHA-256 записывается в archive_manifest.
- Перед любыми сетевыми запросами все запрошенные symbols проверяются на присутствие в snapshot и USDT LinearPerpetual eligibility. Диапазон каждого инструмента клиппируется независимо: начало — ceil(launchTime / interval) до полного candle open, end-exclusive — floor(deliveryTime / interval), если deliveryTime задан. Если overlap пустой, запуск прекращается до скачивания данных.
- Archive manifest содержит requested/effective ranges, lifecycle bounds/status и snapshot provenance. Workflow в `main` и research branch синхронизированы по обязательному `universe_snapshot` input; workflow checkout-ит research branch для исполнения кода.
- Offline tests: [41699298514](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41699298514), [41699364406](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41699364406), [41699423701](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41699423701) — SUCCESS. Compile + archive collector tests passed. Это не реальные API downloads и не PnL.
- Ограничение сохраняется: текущий lifecycle snapshot не доказывает полноту исторического universe, не восстанавливает временные suspension intervals и не гарантирует полный retention delisted contracts в Bybit instruments-info.
