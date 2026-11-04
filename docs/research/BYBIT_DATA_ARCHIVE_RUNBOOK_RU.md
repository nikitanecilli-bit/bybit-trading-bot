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

**Статус публикации collector workflow (обновлено 2026-11-03):** четыре необходимых collector workflow доступны в default branch `main`: три исходных workflow опубликованы через PR #8 (`a0ceb66d9b2cf818b3a24d723130d1125c8ca382`), а `bybit-linear-universe-history.yml` добавлен отдельным commit `49fb4c42aae2c41f008e5668e79680aaf123a026`. Все они явно checkout-ят `research/market-regime-v1-main`, запускают код из этой ветки и сохраняют архивы обратно туда. Дополнительно в `main` опубликованы два ручных H1 workflow entry point: top-5 selector и shared-capital validation; оба checkout-ят research branch, а selector коммитит manifest обратно в неё. Два H1 workflow entry point также опубликованы в `main`; оба checkout-ят research branch (см. раздел 12). PR #4 целиком для этого не использовать: он сильно diverged.

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

- [x] Опубликовать четыре необходимых collector workflow в `main`: три workflow через PR #8 и `bybit-linear-universe-history.yml` отдельным commit `49fb4c42aae2c41f008e5668e79680aaf123a026`. Они намеренно checkout-ят `research/market-regime-v1-main`, где остаются Python-модули и зависимости; переносить весь PR #4 нельзя.
- [x] Опубликовать в `main` ручные H1 entry points: `h1-top5-train-selection.yml` (commit `6e4dc5c95e88b6916570f199986ab48f654ec9a8`) и `h1-shared-capital-portfolio-validation.yml` (commit `837c15f1c8767d97670d160a8389231d622ba858`). Они запускаются на `ubuntu-latest`, checkout-ят research branch; selector коммитит manifest в research branch, validation только читает и публикует отчёт.
- [x] Добавить три collector workflow в default branch. H1 validation workflow остаётся только в research branch.
- [ ] Отдельно решить и реализовать расписание snapshots после успешного первого ручного сбора; сейчас `schedule`/cron отсутствует.
- [ ] Проверить, что self-hosted runner зарегистрирован и имеет label `self-hosted`, а egress country не US/CN. Доступных через текущую GitHub-интеграцию сведений о registered runners нет, поэтому этот пункт пока UNVERIFIED.
- [ ] Запустить сначала snapshots, затем ограниченный архив H1 и проверить coverage/artifacts до любого PnL.


## 9. Per-symbol lifecycle clipping (2026-11-03)

- Архиватор больше не использует один и тот же сырой интервал для всех символов без проверки жизненного цикла.
- Для каждого запрошенного тикера обязателен конкретный Bybit linear universe snapshot из repository checkout. Входной файл проверяется по структуре и SHA-256 включается в archive manifest.
- Границы считаются консервативно на уровне полных свечей: `effective_start = max(requested_start, ceil(launchTime / interval) * interval)`; `effective_end = min(requested_end, floor(deliveryTime / interval) * interval)`, если deliveryTime задан. Для бессрочного контракта deliveryTime=0, верхней границей остаётся requested_end.
- Если тикер отсутствует в snapshot или пересечение не содержит полного бара, сбор прекращается до начала сетевых запросов. Это намеренный fail-closed подход.
- Дополнительные fail-closed проверки: requested start/end должны быть H1-aligned ещё до первого API-запроса; duplicate symbols в snapshot запрещены; PreLaunch/PendingOpen исключаются; для Settling/Delivering/Closed без deliveryTime архиватор отказывает, поскольку верхняя lifecycle-граница неизвестна.
- Snapshot отражает только зафиксированный состав и lifecycle Bybit на момент сбора. Он не доказывает полноту исторического universe, не восстанавливает временные приостановки торгов и не гарантирует, что Bybit сохраняет все делистнутые контракты в endpoint. Неизвестный/отсутствующий инструмент не должен молча считаться «не торговался».
- Workflow в `main` и соответствующий workflow в research branch синхронизированы по обязательному input `universe_snapshot`; исполняемый Python collector остаётся в research branch, которую workflow checkout-ит явно.

## 8. Статическая перепроверка 2026-11-03

- Collector YAML в `main` существует и остаётся manual-only. В доступной GitHub-интеграции этой сессии нет операции `workflow_dispatch` и нет чтения списка зарегистрированных self-hosted runners; поэтому фактический запуск и runner availability не подтверждены.
- Archive downloader сохраняет trade H1 candles в диапазоне [start, end_exclusive), но funding history проверяет включительно до end_exclusive, поскольку settlement может произойти ровно на закрытии последней свечи. Если dated funding schedule содержит settlement на этой границе, дополнительно запрашивается Mark Price candle с open timestamp=end_exclusive; этот дополнительный mark не расширяет торговый OHLCV диапазон. Запросы режутся на bounded windows, CSV пишутся атомарно, насыщенные 200-row funding pages рекурсивно делятся.
- Coverage gate проверяет наличие funding событий, mark candles на каждом funding timestamp, полное покрытие trade H1 marks и допускает ровно один дополнительный Mark candle только на точном terminal close boundary последней trade-свечи. Любые пропуски или дополнительные timestamps в других местах блокируют preflight. Это проверка целостности, а не доказательство корректности самих рыночных цен/ставок или exchange fills.
- Instrument/risk-limit snapshots являются point-in-time наблюдениями; они не восстанавливают исторические параметры до первого сохранённого снимка.
- Никаких новых PnL запусков не выполнялось: Bybit archive и датированные snapshots пока отсутствуют. Следующий реальный эксперимент не запускать до появления этих данных.


**Детерминированные collector tests:** Research CI [#41689536499 — SUCCESS](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41689536499) выполнен на исследовательской ветке; все шаги успешны, включая instrument snapshot collector, risk-limit snapshot collector, market-history archive collector и funding/mark coverage preflight. Это offline/mock tests, не сетевой сбор реальных Bybit данных.




### Funding boundary semantics — уточнение от 2026-11-04

- end_exclusive_ms остаётся границей trade H1 OHLCV: последняя торговая свеча начинается в end_exclusive_ms - 1h и закрывается в end_exclusive_ms.
- Funding endpoint запрашивается до end_exclusive_ms включительно (endTime=end_exclusive_ms), а sidecar и dated settlement schedule должны подтверждать query/schedule coverage до этой же точки.
- Если расписание Bybit funding требует settlement точно в end_exclusive_ms, Mark Price архив включает одну дополнительную свечу с timestamp end_exclusive_ms. Она нужна только как точный Mark-open proxy для funding settlement на close boundary; торговый OHLCV ряд остаётся end-exclusive.
- Coverage validator допускает только этот один дополнительный terminal Mark timestamp. Отсутствующая mark-свеча, extra timestamp в середине ряда или extra mark за пределами одной H1-свечи не допускаются.
- Для terminal settlement Mark candle должен быть закрытым на момент архивации. Если граничная Mark-свеча ещё не закрылась, collector завершится ошибкой; не снижать это требование и не подменять её Last Price.
- Если дополнительная terminal Mark-свеча недоступна/ещё не закрыта, collector удаляет частичные per-symbol CSV/manifest/schedule outputs; content-addressed instrument snapshots сохраняются и могут быть безопасно переиспользованы при повторе в том же output root.

## 10. Train-only top-5 selector v2 — одинаковая выборка кандидатов (2026-11-03)

- Аудит выявил методологическую проблему прежнего selector v1: каждый инструмент оценивался на своей доступной части training window. Наличие минимум 3,000 баров и последующая проверка overlap только у выбранной пятёрки не делали expectancy/PF разных кандидатов напрямую сопоставимыми.
- Selector v2 сначала определяет кандидатов, активных на training cutoff и имеющих минимум 3,000 training bars, затем строит точное пересечение их H1 timestamp ranges. Каждый кандидат replay-ится только на одном и том же общем интервале и с одним и тем же числом баров.
- Если общее окно меньше 3,000 H1 баров, selector завершается fail-closed и не формирует top-5. Reserve-5 также проверяется на общий overlap.
- Изменён protocol id на `h1-top5-train-only-v2`; H1 runner принимает только v2 manifest. Старые v1 manifests несовместимы и должны быть пересозданы.
- Добавлен детерминированный тест общей временной сетки. Research CI [#41702488088](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41702488088) — SUCCESS, 50/50 steps; selector test и runner execution gate прошли.
- Это исправление сопоставимости train-only ranking, не рыночный результат. Selector пока не запускался: нет Bybit H1/funding/mark архивов и датированных instrument/risk snapshots. PnL не рассчитывался.


## 11. Публикация universe-history workflow в main (2026-11-03)

- Проверка показала, что runbook требовал запускать `Archive Bybit linear universe history`, но соответствующий `.github/workflows/bybit-linear-universe-history.yml` существовал только в research branch и отсутствовал в default branch `main`. Manual `workflow_dispatch` workflow из не-default branch нельзя считать доступным для обычного запуска из Actions UI.
- Узкое исправление: добавлен только этот workflow в `main` (commit `49fb4c42aae2c41f008e5668e79680aaf123a026`). Он использует self-hosted runner, проверяет egress country, checkout-ит research branch, запускает point-in-time universe collector и коммитит snapshot обратно в research branch.
- Теперь в `main` опубликованы все четыре нужных коллектора: instrument specs, risk tiers, linear universe history и OHLCV/funding/mark archive. H1 selector/validation и Python research modules остаются в research branch.
- Workflow не запускался: self-hosted runner availability не подтверждена. Это публикация/исправление orchestration, не реальный API download и не PnL.


## 12. Публикация H1 workflow entry points в main (2026-11-03)

- GitHub требует, чтобы файл workflow с `workflow_dispatch` существовал в default branch, иначе manual dispatch не регистрируется. H1 selector и H1 shared-capital validation до этого существовали только в research branch, поэтому нельзя было считать их доступными для ручного запуска из Actions UI.
- В `main` опубликованы два узких entry point:
  - `.github/workflows/h1-top5-train-selection.yml` — commit `6e4dc5c95e88b6916570f199986ab48f654ec9a8`; запускает train-only selector на `ubuntu-latest`, checkout-ит research branch и коммитит selection manifest/ranking обратно в research branch.
  - `.github/workflows/h1-shared-capital-portfolio-validation.yml` — commit `837c15f1c8767d97670d160a8389231d622ba858`; запускает strict shared-capital replay на `ubuntu-latest`, checkout-ит research branch и публикует CSV/manifest artifact. Он не отправляет ордера и не обращается к private account API.
- Эти workflow entry points — manual-only. Для selector нужны уже собранные Bybit H1/funding/mark CSVs, dated instrument/risk snapshots и universe snapshot. Validation дополнительно требует успешный v2 selection manifest.
- Workflow не dispatch-ились; это публикация оркестрации, не запуск selector, не PnL и не paper trading.


## 14. Пауза на внешние Bybit-зависимости по решению пользователя (2026-11-03)

- До появления кандидата со значительной устойчивой чистой доходностью не регистрировать self-hosted runner, не запускать collector workflow, не скачивать новые Bybit market archives и не подключать private/account API.
- Опубликованные workflow остаются подготовленной, но неиспользуемой инфраструктурой. Их наличие в `main` не является разрешением или задачей на запуск.
- Текущий этап ограничен статическим аудитом, исправлением подтверждённых дефектов, deterministic/unit/regression tests и анализом уже имеющихся архивов. Новые рыночные PnL sweeps запрещены до закрытия аудиторских gates и предварительной фиксации следующей гипотезы.
- Возвращаться к Bybit-native execution validation только после того, как на бумаге получен устойчивый положительный кандидат и конкретная следующая проверка действительно может изменить решение о его пригодности.
- Не путать публичные market-data endpoints (которые технически не требуют private API key) с разрешением пользователя на их сбор: сбор также отложен.

## 13. Workflow/code provenance and final selection boundary hardening (2026-11-03)

- Main-branch H1 workflow wrappers explicitly checkout `research/market-regime-v1-main` and record the checked-out SHA as `H1_RESEARCH_CHECKOUT_SHA`. This avoids confusing the main-branch workflow-dispatch commit with the research code commit actually replayed.
- The selector manifest records `research_git_commit`, `workflow_definition_commit` and `workflow_definition_ref`. The H1 validation report records `git_commit` as the research checkout SHA and separately records workflow-definition commit/ref.
- The H1 runner now always checks the selection cutoff against the first 50% validation boundary, including when running `confirm` mode (which scores only fold 3). This prevents a selection cutoff in explore folds 1–2 from passing merely because confirm starts at 80%.
- Regression tests cover workflow-vs-code commit provenance and the confirm-mode 50% selection boundary. Latest Research CI [#41704302480](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41704302480) — SUCCESS, 50/50 steps.
- These are provenance/leakage safeguards only; no Bybit archive was downloaded and no PnL was run.


## 13. Funding collection provenance gate (2026-11-03)

The active `scripts/archive_bybit_market_history.py` collector writes a per-symbol sidecar beside each funding CSV: `SYMBOL.csv.audit.json`. It records every Bybit V5 Funding History query window, page row counts/bounds, whether a page was saturated, CSV row count and SHA-256. Saturated 200-row responses are marked incomplete and recursively subdivided; only complete leaf query windows count toward coverage. The archive-level `archive_manifest.json` also records the active collector script hash and sidecar references.

Do not edit a Funding CSV after collection. Incremental use of the legacy downloader verifies the previous hash before appending and refuses to re-attest modified bytes.

**This is query/data provenance, not yet proof of settlement completeness.** The H1 runner additionally requires a separately hashed schedule-evidence JSON, based on dated raw Bybit instrument snapshots for that symbol. The current archive workflow's single universe snapshot is point-in-time only; it must not be stretched across an arbitrary historical period. Until the schedule evidence covers the scored fold and expected settlement timestamps match the Funding CSV, the H1 runner will fail closed and no market PnL replay should be started.
