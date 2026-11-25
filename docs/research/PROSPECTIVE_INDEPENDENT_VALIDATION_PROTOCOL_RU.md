# Проспективная независимая проверка — протокол проектирования

**Дата:** 2026-11-25  
**Статус:** DESIGN ONLY / NOT ACTIVATED / NO MARKET PNL / NO PAPER OR LIVE EXECUTION  
**Ветка:** `research/okx-public-data-loader`  
**Связанные документы:**  
- `MINIMUM_VIABLE_EDGE_VALIDATION_RU.md`
- `LOW_FREQUENCY_DONCHIAN48_EMA_H1_PREREGISTRATION_RU.md`
- `OKX_FUNDING_ARCHIVE_QA_2026-11-25_RU.md`

## 1. Решение в одном абзаце

Настоящий независимый holdout можно получить только из будущих timestamp-ов, которые начнутся после фиксации гипотезы, execution contract, кода, cost assumptions и критериев решения. Уже собранный OKX архив за 2025-11-25—2026-11-25 — development/evidence dataset, а не holdout: он частично или полностью пересекается с ранее исследованным календарным периодом. Смена Bybit на OKX не делает эти даты независимыми.

На текущем этапе **не активировать сбор и не запускать PnL**. Сначала требуется решить, какая биржа является целевой для утверждения о результате. Bybit остаётся исходной целевой биржей проекта, но её допустимый публичный data path сейчас не подтверждён и прежние ограничения запрещают подключение/сбор. OKX имеет подтверждённый public-data path для BTC-USDT-SWAP, но это другая биржа и другой execution venue. OKX может стать отдельным venue-specific экспериментом только после явного решения, что результат на OKX сам по себе представляет ценность. Никаких выводов о Bybit из OKX не переносить.

## 2. Что именно может быть независимым

### 2.1 Временная независимость

- Holdout start определяется только после подписания/freeze этого протокола и фиксации всех связанных SHA-256 / commit SHA.
- Предлагаемая граница при активации не раньше следующего полного UTC-дня: `2026-11-26T00:00:00Z`. Это не означает, что сбор уже начат.
- Ни один timestamp после этой границы не может использоваться для выбора символа, параметров, фильтров, stop/target, размера позиции, cost model или venue.
- До окончания периода разрешён только контроль качества данных: полнота, дубли, timestamps, API provenance, instrument-state snapshots. Нельзя смотреть на cumulative PnL, equity curve, win rate или менять правила по промежуточным исходам.
- Период фиксируется календарно заранее (предлагаемый базовый горизонт — 12 месяцев). Нельзя остановить его досрочно из-за хорошего или плохого результата. Если заранее установленная достаточность числа сделок не достигнута, результат объявляется INCONCLUSIVE; продление возможно только по правилу, записанному до начала периода, а не после просмотра результата.
- Любая правка стратегии, execution, cost assumptions или data filters после старта делает текущий holdout потраченным для изменённой версии. Новая версия получает новую дату начала.

### 2.2 Что не является независимостью

- OKX вместо Binance/Bybit на уже просмотренных датах.
- Новый архив старых свечей, даже если ранее он не был загружен.
- Повторный прогон старого периода с исправленным кодом или учётом комиссий.
- Переименование старого fold в holdout.
- Просмотр промежуточного PnL, а затем «небольшая» корректировка правил.

## 3. Кандидат: не переносить старую maker-версию

Ближайший существующий кандидат — H1 Donchian(48)+EMA50/EMA200-up. Но исходная preregistration содержит maker limit execution proxy (offset/penetration/TTL), который не доказывает maker fill, очередь, bid/ask, partial fills или adverse selection.

Минимально жизнеспособный новый кандидат — **отдельная версия TAKER-ONLY / SINGLE-INSTRUMENT**, а не исправление задним числом старой maker-стратегии:

1. Сохранить только один заранее выбранный perpetual-контракт и H1.
2. Сохранить Donchian(48)+EMA50/EMA200-up signal без новых фильтров и без parameter sweep.
3. Entry — market-style fill на следующем H1 open по заранее описанной цене исполнения и с заранее установленным max-chase guard.
4. Все выходные ноги также taker; никаких maker rebate/limit-fill assumptions.
5. Stop/TP/trailing/time-stop lifecycle можно сохранить только после отдельной проверки семантики каждого trigger и fill. Нельзя автоматически считать, что текущие правила полностью совместимы с taker-only.
6. Не использовать leverage в первом минимальном пилоте: позиция полностью обеспечена, liquidation/margin-safety claims исключены. Это отдельная execution/risk версия, а не эквивалент прежней isolated 5x конфигурации. Если пользователь хочет сохранить 5x, D6 effective-time risk tiers становится обязательным.
7. Для неоднозначной H1 свечи заранее зафиксировать консервативный порядок исполнения (например, stop-first, если stop и target могли сработать внутри одной свечи).
8. Funding списывать/начислять только при фактическом settlement timestamp, если позиция существовала в момент расчёта; для linear USDT контрактов использовать соответствующую Mark Price для расчёта notional.
9. Все параметры, sizing, лимиты риска, max holding time, rounding и event ordering должны быть полностью зафиксированы в новой preregistration до начала holdout.

**Важное:** текущая preregistration Donchian(48)+EMA не становится автоматически preregistration taker-only. Для новой версии нужны отдельные deterministic tests и новый frozen code hash. Market-PnL runner пока не создавать и не запускать.

## 4. Venue decision: Bybit и OKX — разные ветви доказательств

| Вопрос | Bybit (исходная цель проекта) | OKX (проверенный пилот) |
|---|---|---|
| Public H1 OHLCV | Доступность для разрешённого окружения не подтверждена | Получен годовой BTC-USDT-SWAP архив |
| Mark Price | Не принят в рамках текущего разрешения | Получен годовой H1 архив |
| Funding | Полная независимая история не принята | 1,095 событий за год, непрерывная сетка, 21/21 overlap с REST realizedRate |
| Lifecycle / effective-time specs | Не приняты | Исторические lifecycle/specs пока не приняты; имеется только текущий snapshot |
| Fee tier | Account-specific условия не подтверждены | Account-specific условия не подтверждены; публичная базовая ставка может использоваться только как консервативная assumption с датой/источником |
| Исполнение | Не подтверждено | Не подтверждено; публичные данные не доказывают реальные fills |
| Статус | BLOCKED BY DATA + PERMISSION | Возможен отдельный prospective research venue, но не подтверждён как доступный/подходящий пользователю execution venue |

**Правило:** если конечная цель — стратегия именно на Bybit, OKX не закрывает Bybit gates. Если пользователь выбирает OKX как целевой venue, нужно отдельное venue-specific утверждение и новая preregistration. Доступность публичного API с GitHub runner не доказывает доступность продукта, аккаунта или деривативов в стране пользователя. Не обходить региональные ограничения.

## 5. Минимальные данные для будущего наблюдения

Для одного выбранного linear perpetual, без cross-sectional universe:

| Gate | Что собирать / фиксировать | Условие приёмки |
|---|---|---|
| D1 | H1 trade OHLCV, raw response, request URL, capture time, SHA-256 | Полная UTC-сетка, закрытые свечи, без дублей; gaps объяснены/восстановлены официальным API |
| D2 | H1 Mark Price | Совпадающая временная сетка; отдельная семантика от trade price; используется для funding notional и только тех trigger, где это заранее указано |
| D3 | Каждый funding settlement, фактический timestamp/rate, interval schedule и formula regime | Нет пропущенных settlement events; точные границы; метод/формула не домысливаются |
| D4 | Instrument state, listing time, trading state, maintenance/halts/delisting notices | Подтверждено, что выбранный контракт существовал и был доступен на всём тестовом интервале |
| D5 | Effective-time contract multiplier, tick, lot, min size/notional, settlement currency | Для каждой даты теста известны действовавшие правила; текущий snapshot не подменяет историю |
| D6 | Risk tiers / maintenance margin | Требуется только если включается leverage, liquidation replay или margin-safety claim; для полностью обеспеченного 1x пилота не заявлять такие выводы |
| D7 | L2 / trades / queue evidence | Можно отложить только если стратегия строго taker-only и нет maker/capacity claims; slippage всё равно стрессуется |
| D8 | Dated maker/taker fee assumptions и stress cases | Fee formula, дата и источник зафиксированы; account-specific tier не выдумывается |

### Исполнение и стоимость

- OKX публикует общую формулу комиссии USDT-margined futures: fee rate × contracts × contract value × fill price. Публичный FAQ показывает пример Lv1 taker 0.05% и maker 0.02%, но уровни зависят от пользователя/объёма и могут меняться. Поэтому 0.05% taker можно использовать лишь как предварительную публичную baseline assumption, не как утверждение о персональном тарифе. Перед freeze cost model нужно повторно сверить официальный региональный fee schedule.
- Для taker-only не использовать нулевой slippage и не выводить его из H1 OHLC. До freeze нужно выбрать фиксированные стресс-сценарии slippage и показать чувствительность к ним. Значения нельзя подбирать после просмотра holdout.
- Комиссия начисляется на каждую исполненную ногу по фактическому notional; funding — отдельный cashflow; leverage не уменьшает notional, с которого рассчитывается trading fee.
- Если execution trigger использует Last/Trade, Mark не подменяет его; если trigger использует Mark, нельзя использовать Last OHLC для определения факта срабатывания.

## 6. Data capture и долговременное хранение

Обычный GitHub Actions artifact с коротким retention не годится как единственное хранилище годового holdout. Для запуска будущего наблюдения сначала нужен постоянный append-only архив:

- один пакет на UTC-день/UTC-месяц;
- raw API bodies и точные request parameters;
- normalized CSV/Parquet, manifest, SHA-256;
- версия downloader и commit SHA;
- все gaps/errors сохраняются; никакой тихой интерполяции;
- опубликованные пакеты неизменяемы; исправления оформляются новым versioned package, а не перезаписью;
- отдельный журнал полноты данных без PnL-метрик;
- контрольные суммы должны позволять повторно проверить архив после окончания holdout.

Возможные способы хранения в GitHub (monthly release assets или versioned data commits) требуют отдельного узкого технического решения и проверки лимитов репозитория. Не считать 7/90-дневные Actions artifacts долговременным архивом. Не создавать новый workflow/collector до отдельного разрешения на сбор и утверждения venue.

## 7. Защита от утечки holdout

Во время будущего окна:
- не показывать и не публиковать performance summary;
- не выбирать другой инструмент из-за его движения;
- не менять threshold, EMA, Donchian, stop/target, sizing, max-chase, fee/slippage cases;
- не менять окно данных после просмотра результата;
- допустимы только data-integrity alerts и восстановление отсутствующих исходных данных без изменения правил;
- любая material code change аннулирует текущий holdout для изменённой версии.

В конце периода — один замороженный replay, полный manifest, все cost cases и решение ACCEPT / REJECT / INCONCLUSIVE по критериям, записанным до старта. Положительный результат остаётся single-instrument, venue-specific candidate; он не доказывает переносимость на другие биржи или гарантированную будущую доходность.

## 8. Блокеры до активации

1. **Выбрать целевой venue:** Bybit остаётся primary и тогда нужно отдельное разрешение/законный доступ к официальным публичным данным; либо OKX становится самостоятельным target venue, не proxy для Bybit.
2. Зафиксировать один конкретный инструмент и подтвердить его доступность для пользователя в применимой юрисдикции без обхода ограничений.
3. Выпустить отдельную TAKER-ONLY preregistration, закрыв trigger/fill semantics, risk sizing и all-in cost scenarios.
4. Закрыть D1–D5 для выбранного venue; D6 — если leverage; D7 — если maker/capacity claims; D8 — до любого PnL.
5. Утвердить долговременное append-only хранение на весь будущий период.
6. Только после этого отдельно разрешить public-data collection. Сбор не должен содержать account/private endpoints, ключей, логина, ордеров, paper/live execution.

## 9. Что делаем сейчас

- Сохраняем текущий статус **DESIGN ONLY / NOT ACTIVATED**.
- Не трогаем `main`, основную ветку стратегии и Bybit workflows.
- Не начинаем сбор будущих данных, не запускаем backtest/PnL/sweep/event study.
- Следующий реальный decision gate — выбор целевого venue. До него дальнейшее расширение загрузчика было бы преждевременным.

## Источники

- [OKX API v5 — official API documentation](https://www.okx.com/docs-v5/en/)
- [OKX historical market data API guide / changelog](https://www.okx.com/docs-v5/log_en/) — каталог historical market data supports monthly/daily modules; availability varies by instrument/module/time.
- [OKX Trading Fee Rules FAQ](https://www.okx.com/help/trading-fee-rules-faq) — fee tiers, futures fee calculation and examples; actual user tier may differ.
- [OKX Perpetual Futures Guide](https://www.okx.com/en-eu/help/i-perpetual-swaps) — contract and funding mechanics.
