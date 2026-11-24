# Минимальный путь к доказательству торгового преимущества

**Дата пересмотра:** 2026-11-24  
**Статус:** DESIGN / NO DATA COLLECTION / NO MARKET PNL AUTHORIZATION  
**Управленческая основа:** `docs/COMPANY_OPERATING_PHILOSOPHY_RU.md`

## 1. Задача

Не строить универсальную платформу и не восстанавливать всю историю всех контрактов до появления конкретной причины. Найти минимальный эксперимент, который способен достоверно опровергнуть или поддержать одну заранее зафиксированную торговую гипотезу.

Минимальный эксперимент не равен слабому эксперименту. Он может сузить охват, но не должен снижать достоверность вывода в пределах заявленного охвата.

## 2. Сначала кандидат, затем данные

До получения данных нужно выбрать ровно одну гипотезу, которая:
- полностью определяет сигнал, вход, выход, отмену, максимальное время удержания, частичное закрытие и поведение при неоднозначном баре;
- имеет frozen parameters и заранее зафиксированную причину существования;
- не требует подбора параметров на тестовом периоде;
- допускает однозначный расчёт gross/net cashflows;
- имеет заранее записанные ACCEPT / REJECT / INCONCLUSIVE критерии.

Текущая пригодность кандидатов:
- **H1 baseline / Donchian(48)+EMA50/200 preregistration:** есть более полный торговый lifecycle и отдельная preregistration `LOW_FREQUENCY_DONCHIAN48_EMA_H1_PREREGISTRATION_RU.md`. Но все старые proxy folds уже исследованы; новая preregistration не превращает их в независимую выборку. Старые net-PnL дополнительно непригодны из-за exit-cost accounting defect. В preregistered исполнении maker limit fill основан на OHLC penetration (20/5 bps), без bid/ask, очереди и partial fills; это не доказанный maker execution. Повторное использование тех же периодов для подбора или доказательства запрещено.
- **H-B:** подтверждены только причинная механика сигнала и геометрия входа на следующем H1 open. Нет утверждённого полного lifecycle, execution model, sizing, persistence и market PnL. Состояние остаётся FROZEN; этот документ не размораживает H-B и не придумывает недостающие правила.
- **H-A / H-C:** не возвращать в tuning на использованных выборках.

**Текущий runner не является готовым single-symbol pilot:** `run_h1_shared_capital_portfolio_validation.py` требует точное совпадение с frozen train-only Top-5 manifest, lifecycle universe snapshot и directories для kline/funding/mark/specs/risk tiers; он перебирает заранее заданные folds, arms и cost multipliers. Переделка его под один символ была бы отдельной инженерной задачей, а не простой настройкой. Не создавать новый runner до доказательства, что он необходим для выбранного независимого эксперимента.

**Вывод:** сейчас нет кандидата, одновременно готового к честному новому PnL validation и имеющего независимый допустимый период/реалистичную модель исполнения. Это отдельный блокер наряду с данными. Не маскировать его сбором ещё большего архива или инфраструктурой.



## 2A. Решение по готовности кандидатов — read-only review 2026-11-24

### Ранжирование по близости к честной проверке

| Кандидат | Что уже есть | Что блокирует | Решение |
|---|---|---|---|
| **H1 Donchian(48)+EMA50/200** | Frozen signal specification; полный общий engine lifecycle (entry, sizing, stop/TP/trailing/time stop, funding, fees, risk state); отдельная preregistration | Текущий runner принудительно превращает сигнал в maker limit: offset 20 bps, penetration 5 bps, TTL 3 H1 bars. OHLC penetration не подтверждает maker fill, queue, spread или partial fills. Runner также привязан к Top-5 manifest/folds и 5x isolated risk-tier path. Все старые proxy folds просмотрены | **Ближайший к спасению кандидат, но не готов к validation.** Не использовать текущую maker-fill версию как доказательство исполнимости |
| **H-B mean reversion** | Causal signal, stabilization and next-open geometry tests | Нет полного lifecycle, stop/target/exit policy, sizing, portfolio interaction, funding/cost integration | FROZEN. Достраивание lifecycle сейчас дороже, чем адаптация существующего H1 engine |
| **H-A / H-C** | Исследованные конфигурации и/или synthetic mechanics | Нет положительного независимого edge; старые folds уже использованы | Не возвращать в tuning |

### Технически самый дешёвый следующий вариант для H1

Read-only code inspection выявил важную возможность: базовый engine `_try_fill_pending()` уже поддерживает **market entry на open следующей H1 свечи**, когда сигнал имеет `order_type != "limit"`. Для market entry он проверяет max-chase, использует следующий open и рассчитывает taker fee/slippage в sizing/accounting. Но текущий research runner оборачивает этот метод, принудительно задаёт `order_type="limit"` и применяет OHLC limit-wait модель. Runner config также задаёт `maker_entry_and_tp1=True`, а `maker_tp1_and_target=False`.

Поэтому минимальная инженерная ветка — сохранить H1 Donchian(48)+EMA signal и существующий lifecycle, но создать **отдельную preregistered taker-only execution profile**:
1. вход market на open следующей H1 свечи, с существующим max-chase guard;
2. taker fees/slippage на entry и всех exit legs; maker assumptions выключены явно;
3. прежние stop/TP/trailing/time-stop правила сохраняются только после проверки, что их trigger/fill semantics не зависят от maker assumptions;
4. один заранее выбранный инструмент, без Top-5 ranking и cross-sectional claims;
5. прежние folds не использовать как independent validation; thresholds/parameters фиксировать до нового test period.

Это **не та же самая preregistered maker strategy** и не подтверждение её результата. Изменение execution contract требует новой версии preregistration и deterministic tests. Никакой market-PnL расчёт не запускать до снятия запретов и приёмки данных.

### Что такой путь снимает и что не снимает

- Убирает необходимость доказывать maker queue priority, если все ноги действительно taker (D7 можно не включать в первый тест).
- Не убирает D1 Bybit-native trade OHLCV, D3 funding completeness, D4 lifecycle выбранного символа, D5 effective-time specs и D8 fee assumptions.
- При сохранении 5x isolated leverage **D2 Mark и D6 risk tiers остаются обязательными** для liquidation/risk replay. Нельзя считать D6 необязательным лишь потому, что выбран один символ.
- Top-5 manifest можно исключить только из нового single-symbol design; это не превращает прежние cross-sectional folds в holdout.
- Пока нет принятого независимого периода и требуемых Bybit-native inputs, кандидат остаётся BLOCKED.

### Решение

**Не строить новый runner сейчас.** Сначала требуется read-only доказательство, что один символ и независимый период могут быть обеспечены источниками с достаточной provenance. Если такой путь подтверждается, следующая инженерная задача — отдельный taker-only single-symbol adapter поверх существующего engine, а не новая стратегия и не переписывание всего движка. Если источника нет, остановиться на BLOCKED.


## 3. Минимальный scope данных

После выбора кандидата следует проверить возможность узкого single-instrument исследования на одном заранее выбранном Bybit Linear perpetual, одном H1 timeframe и одном общем временном окне. Конкретный символ и период фиксируются до просмотра результатов. Никакого cross-sectional ranking, top-N selection или многосимвольного portfolio claim на первом проходе.

Узкий scope уменьшает требования к широкому point-in-time universe, но не отменяет доказательство того, что выбранный контракт существовал и был доступен для торговли на всём заявленном интервале.

### Обязательное для ограниченного single-instrument net-PnL candidate

| Gate | Минимальное доказательство | Что остаётся вне утверждения |
|---|---|---|
| D1 Trade OHLCV | Exchange-native Bybit Linear H1, исходная семантика timestamps, непрерывная сетка, raw provenance, SHA-256, gap/duplicate report | Не доказывает очередь, spread или реальные fills |
| D2 Mark | Датированные Mark Price candles на тех временных точках, где mark нужен для trigger/risk/valuation; отдельная семантика от trade OHLCV | H1 mark candle не является tick-level trigger tape |
| D3 Funding | Все settlement events в окне, query/page provenance, exact timestamp, interval schedule evidence, boundary coverage и отдельный completeness check | Текущий funding interval нельзя переносить в прошлое без доказательства |
| D4 Lifecycle | Историческая доступность выбранного контракта на всём окне; подтверждение listing/trading/pauses/delisting и явные причины gaps | Не разрешает выводы о других контрактах и cross-sectional universe |
| D5 Specs | Effective-time tick/qty/min-notional/contract multiplier/settlement currency для выбранного контракта и периода | Не разрешает переносить параметры на другие символы |
| D8 Fees | Зафиксированный консервативный taker-fee scenario и stress scenario с источником/датой | Не утверждать account-specific fee tier |

D6 не требуется для узкого результата, который **явно не заявляет leveraged liquidation/risk replay**, только если дизайн использует полностью обеспеченную позицию без leverage и заранее ограничивает выводы. Если применяется leverage, моделируется liquidation или утверждается margin safety — D6 становится обязательным.

D7 L2/trades не нужен для maker-fill утверждений, если эксперимент с самого начала использует только taker execution и консервативные заранее зафиксированные slippage stress cases. Любое утверждение о maker profitability, queue priority, partial-fill probability или capacity требует D7 и отдельной модели.

Это ограничение scope, а не обход gates. Нельзя использовать отсутствие D6/D7, чтобы делать более широкие утверждения, чем позволяет эксперимент.

## 4. Funding: дополнительная версия экономического режима

Funding нужно учитывать не только как ряд ставок и timestamp-ов. В manifest также сохраняются:
- effective funding interval;
- подтверждённая формула/версия расчёта и её effective window, если применимо;
- исходный announcement или другой первичный источник;
- публикационное и фактическое effective time;
- точная граница неопределённости, если список rollout неполон.

Объявление Bybit от 2026-11-19 сообщает о поэтапном изменении формулы funding с 2026-11-24: расчёт масштабируется с 8-часовой базы к фактическому funding interval. Rollout идёт несколькими партиями до 2026-12-01; приведённый в объявлении список символов прямо обозначен как non-exhaustive. Поэтому нельзя назначить effective date конкретному контракту по одному общему announcement date. Для realised historical funding cashflow используем фактически опубликованную settlement rate; версия формулы нужна для режима/происхождения и любых прогнозных допущений.

## 5. Минимальная execution-модель первого прохода

Для первого ограниченного исследования:
- только taker-style entry/exit; maker fills не моделировать;
- entry timestamp и цена строго соответствуют заранее зафиксированному правилу;
- stop/target trigger source указан отдельно (Mark или Last/Trade); нельзя смешивать источники;
- при неоднозначности H1 бара, где могли сработать и stop, и target, применяется заранее зафиксированное консервативное правило (по умолчанию stop-first);
- комиссии считаются от фактического execution notional каждой ноги;
- slippage проверяется несколькими заранее заданными стресс-сценариями, не подбираемыми под положительный результат;
- funding применяется по точным settlement timestamp только к позиции, открытой на момент settlement;
- округление цены и количества выполняется по effective-time D5;
- все исключения, пропуски и неопределённости сохраняются в manifest.

Такой тест может дать только **single-instrument historical edge candidate under stated assumptions**. Он не доказывает cross-asset generalization, maker edge, масштабируемость, portfolio diversification или будущую прибыль.

## 6. Независимость и критерии решения

- Все параметры и правила фиксируются до просмотра test outcomes.
- Уже использованные E01–E13 folds не становятся holdout из-за смены названия эксперимента или источника файлов.
- Если гипотеза ранее отбиралась на том же инструменте/периоде, новый replay на тех же timestamp-ах — robustness/accounting check, не независимая репликация.
- Положительный single-symbol результат — только candidate; далее требуется действительно независимый период/инструмент и forward/paper gate.
- Отрицательный результат закрывает проверенную конфигурацию, если качество данных и исполнения достаточно для такого вывода.
- Если funding completeness, lifecycle или execution ambiguity не разрешены, результат INCONCLUSIVE/BLOCKED, а не условный PASS.

## 6A. Проверка независимого периода и существующего Bybit holdout path (2026-11-25)

Read-only audit Section 49 of the acceptance ledger confirms that the repository has no accepted independent dataset for H1 Donchian(48)+EMA50/200. CryptoFetch proxy bars end by 2026-10-27 and were already used in E01–E13 and subsequent H1 hypothesis work. The preregistration dated 2026-11-04 does not make those bars unseen.

The existing scripts/run_bybit_h1_long_only_holdout.py is not a substitute: it runs Donchian(20), uses 11 symbols selected on earlier Binance training data, launches independent 10,000-USDT per-symbol simulations rather than shared capital, applies an upper-bound funding approximation, and explicitly states that its Bybit calendar period overlaps the earlier Binance study. It also requires Bybit market files absent from the repository.

The existing archive workflow defaults to self-hosted and warns hosted US runners are blocked. Self-hosted runners and new collectors remain prohibited. Do not modify the workflow or relabel old folds as holdout.

Decision: **BLOCKED BY DATA + INDEPENDENCE**. No runner rewrite or PnL run is justified until a permitted independent Bybit-native dataset exists and passes the relevant gates.

## 7. Что делать сейчас

Пока действуют ограничения пользователя:
1. Не подключать Bybit API, кроме отдельно разрешённого публичного announcements endpoint.
2. Не скачивать market archives, не запускать collectors и не настраивать self-hosted runner.
3. Не выполнять market-PnL backtests, sweeps или event studies на текущем proxy package.
4. Продолжать только read-only audit публичной документации/объявлений, существующего кода, Git history и уже сохранённых артефактов.
5. Не менять H-B lifecycle и не выбирать новые параметры без отдельного обоснования и разрешения.

**Следующий допустимый результат:** выбрать один полностью специфицированный кандидат и доказать наличие действительно независимого допустимого периода/данных. Если такого сочетания нет, честный статус — BLOCKED; не создавать работу ради видимости движения.
