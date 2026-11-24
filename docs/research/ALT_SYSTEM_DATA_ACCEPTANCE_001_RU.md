# ALT-SYSTEM-DATA-ACCEPTANCE-001 — контракт приёмки рыночных данных

**Дата:** 2026-11-05  
**Ветка:** `research/market-regime-v1-main`  
**Статус:** SPECIFICATION ONLY — источники не загружались и не проверялись  
**Цель:** определить минимальные условия, при которых исторические данные можно допустить к исследованию автономной системной торговли альткоинами на Bybit USDT Perpetual.

> Этот документ не подтверждает наличие данных и не разрешает их сбор. Все поля источника до фактической read-only инвентаризации имеют статус `unverified`. Никаких рыночных PnL-тестов до прохождения всех обязательных gates.

## 1. Принципы

1. **Point-in-time first.** Состояние universe и спецификаций должно быть известно на момент каждого решения, а не восстановлено из текущего списка контрактов.
2. **Exchange-native identity.** Bybit-native данные и сторонние proxy-данные хранятся и маркируются раздельно. Proxy нельзя переименовать в Bybit history.
3. **No silent repair.** Пропуски, дубликаты, out-of-order события, конфликтующие записи и коррекции не удаляются молча. Каждое преобразование отражается в manifest.
4. **Causal timestamps.** Сигнал использует только данные, доступные к моменту принятия решения. Время открытия/закрытия бара, публикации и доступности данных различаются.
5. **Reproducible package.** Каждый принятый набор должен быть неизменяемым пакетом с manifest, checksums, schema version и точными правилами построения.
6. **Portfolio completeness.** Universe, цены, funding и contract specs должны покрывать одну и ту же временную область для всех включённых инструментов.
7. **Fail closed.** Неизвестная полнота обязательного источника означает BLOCKED, а не условный PASS.

## 2. Обязательные источники и критерии

| ID | Источник | Минимальные поля | Жёсткий критерий приёмки | Если не выполнено |
|---|---|---|---|---|
| D1 | Bybit linear trade OHLCV | symbol, interval, bar_start_utc, bar_end_utc, open/high/low/close, volume, turnover, source timestamp | Bybit-native происхождение; документированная семантика свечи; UTC; уникальный ключ symbol+interval+bar_start; непрерывная ожидаемая сетка для выбранного периода; OHLC invariants | BLOCKED для signal/PnL |
| D2 | Mark Price history | symbol, timestamp_utc, mark_price, source timestamp | Покрытие всех включённых символов и времён, когда mark требуется для valuation/risk/liquidation; однозначная частота и семантика | BLOCKED для полного PnL/risk |
| D3 | Funding history | symbol, funding_rate, funding_interval, settlement_timestamp_utc, published/available timestamp, settlement mark если доступен | Все settlement events в окне; отсутствие необъяснённых пропусков; корректное применение только к позиции, открытой на settlement | BLOCKED для net PnL |
| D4 | Point-in-time instrument universe | symbol, category, listing_time, trading_start, status transitions, delisting_time/last_trade_time, source/effective timestamps | Историческая реконструкция доступности каждого контракта; включены delisted/expired/paused symbols и причины исключения | BLOCKED для cross-sectional research |
| D5 | Effective-time instrument specs | symbol, effective_from/to, tick_size, qty_step, min_order_qty, min_notional/value rules, contract multiplier, settlement/quote currency, status | Каждое изменение имеет effective time; покрытие всего backtest interval; округление и допустимость ордеров воспроизводимы | BLOCKED для sizing/execution |
| D6 | Risk limits / tiers | symbol, effective_from/to, risk tier, max leverage/position value, maintenance margin parameters and source | Исторические изменения лимитов покрыты; точная семантика полей известна | BLOCKED для leveraged portfolio risk |
| D7 | Trades / L2 (только maker/execution study) | exchange event timestamp, receive timestamp if available, sequence/update IDs, price, size, side; snapshots + deltas for book | Восстанавливаемая книга, sequence continuity, достаточная частота и покрытие символов; timestamp semantics документирована | Maker claims BLOCKED; не блокирует только market/taker proxy study |
| D8 | Fees (execution/accounting) | symbol/category, maker/taker rate, effective interval, source, tier assumptions | Публичная базовая ставка или документированная фиксированная ставка сценария; не выдавать account-specific unknown за факт | Net PnL BLOCKED либо только явно маркированные сценарии |

**Важно:** D1–D6 обязательны для полного портфельного исследования. D7 требуется до любых утверждений о фактическом maker fill или maker profitability. D8 должен быть известен либо консервативно задан как сценарий с отдельным stress case; фактическую ставку аккаунта нельзя предполагать.

## 3. Общие правила качества

### 3.1 Временная модель

- Все внутренние timestamps нормализуются в UTC, исходное значение и исходная timezone сохраняются.
- Хранить отдельно: `event_time`, `published_time`, `received_time` (если доступно), `effective_from`, `effective_to`.
- Для свечей зафиксировать, означает ли timestamp начало или конец интервала. Нельзя смешивать обе конвенции в одной серии.
- Для решений на закрытии бара сигнал не может использовать данные, появившиеся после этого закрытия.
- Funding привязывается к фактическому settlement timestamp, а не к округлённому часу или времени записи в файл.
- Порядок событий с одинаковым timestamp должен быть детерминирован и описан.

### 3.2 Структурные проверки

Для каждой строки D1:
- `low <= min(open, close) <= max(open, close) <= high`;
- цены и объёмы конечны; цены строго положительны; объёмы/turnover неотрицательны;
- отсутствуют дубликаты ключа;
- symbol и interval принадлежат manifest;
- временная метка выровнена по ожидаемой сетке интервала.

Для D2–D8:
- цены и размеры проходят типовые/знаковые проверки;
- effective intervals не пересекаются для одной версии параметра, если источник явно не задаёт приоритет;
- sequence gaps и несогласованные snapshots/deltas фиксируются как дефекты, а не заполняются догадкой;
- все единицы измерения и contract multipliers явно определены.

### 3.3 Coverage и gaps

- Рассчитать ожидаемое число записей отдельно для каждого symbol/source/interval.
- Составить gap report: число, диапазоны, максимальная длина и доля пропусков.
- Различать отсутствие торгов, отсутствие публикации и отсутствие записи в выгрузке. Нулевой объём допустим только если источник действительно кодирует его как валидный бар.
- Не интерполировать OHLC, mark, funding или universe lifecycle для закрытия дыр.
- Дубликаты классифицировать: идентичные, конфликтующие, повторная доставка. Правило дедупликации должно быть детерминированным и сохранять raw count.
- Out-of-order события сохранять в raw layer и отдельно учитывать в normalized layer.

## 4. Point-in-time universe

На каждую decision timestamp строится universe только из контрактов, которые:
- уже были доступны для торговли к этому времени;
- имели подходящий статус и необходимые спецификации;
- удовлетворяли заранее установленным liquidity/tradability фильтрам, рассчитанным только на прошлых данных.

Обязательно:
- сохранять listing, suspension/resume, delisting и last-trade lifecycle;
- сохранять исключённые символы и точную причину исключения;
- не использовать текущие top-volume/top-market-cap списки для прошлых дат;
- не исключать delisted символы из исторического знаменателя;
- liquidity ranking использовать lagged окнами, не включающими будущее;
- зафиксировать treatment для миграций symbol/contract и смены contract specs.

## 5. Dataset manifest — обязательная запись на каждый пакет

Минимальная JSON-структура (пример схемы, не фактический manifest):

```json
{
  "dataset_id": "bybit-linear-h1-YYYYMMDD-v1",
  "venue": "Bybit",
  "market_category": "linear",
  "source_type": "exchange_native",
  "source_reference": "documented public source or export reference",
  "retrieved_at_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "schema_version": "1.0.0",
  "normalizer_commit": "git-sha-or-null",
  "coverage": {
    "start_utc": "YYYY-MM-DDTHH:MM:SSZ",
    "end_utc": "YYYY-MM-DDTHH:MM:SSZ",
    "symbols_expected": 0,
    "symbols_present": 0
  },
  "files": [
    {
      "path": "relative/path",
      "sha256": "64-hex-character-digest",
      "bytes": 0,
      "row_count": 0,
      "min_event_time_utc": "YYYY-MM-DDTHH:MM:SSZ",
      "max_event_time_utc": "YYYY-MM-DDTHH:MM:SSZ"
    }
  ],
  "quality": {
    "duplicate_rows": 0,
    "conflicting_duplicate_keys": 0,
    "out_of_order_rows": 0,
    "gap_count": 0,
    "gap_report_path": "relative/path"
  },
  "limitations": [],
  "acceptance": {
    "D1": "unverified",
    "D2": "unverified",
    "D3": "unverified",
    "D4": "unverified",
    "D5": "unverified",
    "D6": "unverified",
    "D7": "unverified",
    "D8": "unverified"
  }
}
```

Manifest должен содержать отдельный file entry для каждого raw/normalized файла. SHA-256 считается по точным байтам файла; изменение нормализации, схемы или исходных данных создаёт новую версию пакета. Значение `null` не заменяется вымышленным SHA или датой.

## 6. Статусы приёмки

| Статус | Значение | Допустимое использование |
|---|---|---|
| `available` | Источник/поле существует, проверен и прошёл конкретные проверки | Только указанные в acceptance scope исследования |
| `partial` | Данные существуют, но покрытие/поля/период неполные | Диагностика с явным scope; не полный PnL |
| `missing` | Источник или обязательное поле отсутствует | Никакого использования как будто данные есть |
| `unverified` | Наличие/происхождение/качество не проверены | Не проходит gate |
| `rejected` | Проверка выявила несовместимость или недостоверность | Исключить до исправления и новой версии manifest |

PASS для D1–D6 требует `available` на одном и том же исследуемом интервале и согласованной вселенной. `partial` нельзя трактовать как PASS для портфельного теста.

## 7. Независимые spot checks

Перед присвоением `available`:
1. Выбрать заранее зафиксированные symbol/date samples, включая периоды высокой волатильности, funding boundaries, листинг/делистинг и обычные дни.
2. Сверить raw записи с независимым официальным Bybit public source/export; сохранить URL/endpoint reference, время проверки и точные сравниваемые поля.
3. Проверить начало/конец интервалов, timezone, цену/объём, funding rate и settlement timestamps.
4. Зафиксировать расхождения, допустимые округления и их обоснование. Не вводить tolerance после просмотра расхождений без новой версии протокола.
5. Сохранить spot-check report и hashes вместе с manifest.

Если независимая сверка невозможна, статус остаётся `unverified`; наличие похожих данных у стороннего провайдера не заменяет проверку происхождения.

## 8. Gate matrix и разрешённые действия

| Gate | Требование | Что разрешает |
|---|---|---|
| G0 — provenance | Источник, метод получения, schema и checksums документированы | Только дальнейшую проверку качества |
| G1 — core prices | D1 accepted; D2 accepted для mark-dependent accounting | Исследование сигналов и ценовой динамики, но не полный net PnL без остальных gates |
| G2 — universe/specs | D4, D5, D6 accepted; PIT lifecycle и effective times покрыты | Исторический cross-sectional universe и корректное sizing/risk |
| G3 — funding/accounting | D3 accepted; settlement events проверены; D8 задан явно | Полный net portfolio PnL в рамках описанной cost model |
| G4 — execution | D7 accepted и воспроизводимая модель queue/partial fills/latency/adverse selection | Только тогда maker execution claims; без G4 использовать консервативный market/taker baseline |
| G5 — experiment preregistration | Frozen hypothesis, features, folds, costs, controls, metrics, rejection rules и untouched holdout | Рассмотрение одного заранее определённого research PnL experiment |

Ни один gate сам по себе не означает, что стратегия прибыльна. Даже G5 не разрешает paper/live promotion.

## 9. Текущее состояние по аудиту от 2026-11-05

Это baseline статусов из read-only аудита репозитория; они не заменяют проверку файлов и manifest.

| Источник | Текущий статус | Основание |
|---|---|---|
| D1 Bybit-native H1 OHLCV | `missing` в проверенном локальном research package | В STRATEGY-REFOCUS-001 не найден полный сохранённый Bybit-native набор для исследуемого периода |
| D2 Bybit Mark | `missing` / `unverified` | Есть workflows/код, но полный исторический package не подтверждён |
| D3 Funding + settlements | `missing` / `unverified` | Полнота и settlement mark не подтверждены |
| D4 PIT universe/lifecycle | `partial` / `unverified` | Есть код/workflows и отдельные snapshots; полный lifecycle/delisted coverage не подтверждён |
| D5 Instrument specs | `partial` / `unverified` | Есть механизмы snapshots, но нет полного effective-time журнала |
| D6 Risk tiers | `partial` / `unverified` | Есть workflow/код, полнота истории не доказана |
| D7 L2/trades | `partial` — один диагностический AAVEUSDT sample; `missing` для репрезентативного execution dataset | Сохранён однодневный sample 2025-09-02 (см. раздел 9.1); n=4 hypothetical orders недостаточно для оценки fill rate |
| D8 Fees | `unverified` | Базовые сценарии есть, но датированные account/symbol-specific ставки не подтверждены |

Шесть CryptoFetch ZIP в репозитории — supplementary proxy input. Они не проходят D1–D6 как Bybit-native market history. Никакой архив не открывался, скачивался или распаковывался при составлении этого документа.

## 10. Запреты до отдельного decision checkpoint

- Не загружать и не распаковывать архивы/рыночные датасеты.
- Не запускать collectors, exchange API calls, приватные/account APIs или любые торговые операции.
- Не выполнять PnL backtests, пересчёт исторического PnL или parameter sweeps.
- Не считать proxy datasets Bybit-native.
- Не заявлять maker fill rate без G4.
- Не менять `main`; не сливать PR #4 или PR #13.

Следующий разрешённый шаг в рамках текущих ограничений — read-only inventory уже существующих файлов и workflow metadata, затем обновление таблицы статусов только на основании проверяемых фактов.


### 9.1. Уточнение D7: существующий однодневный L2/trades sample

Read-only checkpoint фиксирует уже существующий artifact workflow [#41814167058](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41814167058) для AAVEUSDT за 2025-09-02:

- L2 archive: 88,252,368 bytes; SHA-256 `e3646429c600f4917c021e240497e8f3d46fd44ba57168100633181916c761f6`; 816,684 events за 24 часа; ZIP CRC проверен.
- Public trades: 13,095,906 bytes; SHA-256 `cf11d05f6053acfeb22b1112df666ff328034963f04c6e6159f35cae63de1bc1`; 346,131 уникальных trade IDs.
- 66 сделок предшествуют первому matching-engine book timestamp и должны исключаться из replay.
- Четыре вручную заданные hypothetical orders дали fill fractions 58%, 100%, 100%, 33%. При n=4 это только проверка механики, не оценка fill probability и не свидетельство maker profitability.
- Mean signed midpoint markout: 1s −2.73 bps; 5s −0.58 bps; 30s +3.11 bps; 60s +4.09 bps. При n=4 статистические выводы о стабильном adverse selection недопустимы.

Дополнительный предел: статический аудит ENG-EXEC-038 установил, что исторический daily trades CSV adapter не передаёт cross-stream `seq`, поэтому сделки и L2 нельзя надёжно упорядочить внутри одинаковой миллисекунды. Текущий replay консервативно не кредитует same-ms fills. ENG-EXEC-040 подтвердил, что L2 deltas после постановки заявки не списывают очередь вторым каналом: queue consumption идёт только по допустимым public trades. Это избегает прямого двойного списания, но не восстанавливает индивидуальное распределение aggregate-L2 очереди.

**Итог D7:** статус `partial` только для существующего однодневного диагностического sample; для репрезентативного multi-symbol / multi-regime execution research — `missing`. Не скачивать artifact повторно и не запускать replay в рамках текущих ограничений.




## 11. Read-only inventory and external source screening (2026-11-24)

### 11.1. Repository inventory at branch HEAD

Checked the recursive Git tree at commit `a181606b8ec3e2ec9d416fe56cbe07ef92564eb9` (307 tree entries; not a working-tree checkout). Among data-like file extensions (`.zip`, `.csv`, `.parquet`, `.feather`, `.jsonl`, `.db`, `.sqlite`, `.gz`, `.tar`, `.arrow`), the only market-data archives are the six ZIP files under `data/archives/cryptofetch/`. The only other matching JSON file is `scripts/h1_symbol_universes.json`, which is a configuration universe, not a market history dataset.

No committed Bybit OHLCV, mark, funding, trades, L2, dated instrument/risk snapshots, or universe-history archive was found in the current branch tree. No `data/archives/bybit/`, `data/instrument_specs/`, or `data/universe_history/` dataset paths are present. This is a repository-tree statement, not a claim that no files could exist outside this repository.

### 11.2. Correction to the retained AAVE L2 diagnostic evidence

Rechecked the existing GitHub Actions run [#41814167058](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41814167058) through run metadata, job metadata, and its existing job log only. No artifact was downloaded and no market archive was fetched in this audit.

The workflow did download and scan the AAVEUSDT 2025-09-02 L2 archive (88,252,368 bytes; SHA-256 `e3646429c600f4917c021e240497e8f3d46fd44ba57168100633181916c761f6`; 816,684 events) and public trades archive (13,095,906 bytes; SHA-256 `cf11d05f6053acfeb22b1112df666ff328034963f04c6e6159f35cae63de1bc1`; 346,131 rows). However, the workflow upload step retained only three compact JSON inspection reports: `bybit_orderbook_sample_inspection.json`, `bybit_trade_sample_inspection.json`, and `bybit_l2_queue_replay_report.json`. The resulting artifact was only 3,725 bytes (artifact ID `13314017303`, SHA-256 `c6d37b83a909eae2e53e0436d74083dc1cc3d57348e95c0acaf09db7d1146f9c`). The 88 MB L2 and 13 MB trade source archives were not retained in that artifact and are not present in the repository tree.

Additional source-log checks confirm:
- L2 stream: 816,684 events over 24 hours; 2 snapshots and 816,682 deltas; no nonmonotonic timestamps, adjacent duplicate timestamps, cross-sequence reversals, update-ID resets, or missing matching-engine timestamps in the scanned file.
- Trades: 346,131 unique IDs; 66 trades precede the first book matching-engine timestamp; the CSV has an RPI column (all zero in this sample) but **no block-trade field**. The strict replay must reject it; absence of the field is not equivalent to `false`.
- The queue probe contained four deterministic hypothetical orders only and explicitly warned that it was not strategy PnL, a fill-rate estimate, L3 replay, or exchange-confirmed execution.

Therefore D7 remains `partial` for a single historical diagnostic whose source bytes are no longer retained in the repository/artifact; it is `missing` for representative, reproducible multi-symbol execution research. The previous section 9.1 describes the diagnostic values, not a currently available raw dataset.

### 11.3. External candidates found by public documentation screening

These are discovery leads only. No files were downloaded, no account was created, no API was called, and no provider data was accepted.

**Candidate A — Hugging Face, `rogerdehe/klines-bybit`**  
Public dataset card: https://huggingface.co/datasets/rogerdehe/klines-bybit

The card self-reports approximately 617 USDT perpetual pairs including delisted symbols, 1h candles among the available timeframes, history from each listing (mostly 2020–2021 onward), and mark/funding series for most pairs. It also explicitly says the dataset is under construction, pair/timeframe coverage is still growing, per-file coverage documentation is pending, and the data is provided as-is without a completeness/accuracy warranty.

Preliminary fit: possible candidate for D1 and partial D2/D3; the claim that delisted symbols are included does not by itself establish PIT lifecycle completeness for D4. No effective-time instrument specs or risk-tier history are established by the card, so D5/D6 remain missing/unverified. No acceptance without exact file inventory, manifests, provenance, per-symbol gaps, and independent spot checks.

**Candidate B — CryptoHFTData Bybit archive**  
Bybit overview: https://www.cryptohftdata.com/exchanges/bybit  
Order book: https://www.cryptohftdata.com/datasets/bybit-orderbook-data  
Trades: https://www.cryptohftdata.com/datasets/bybit-trades-data  
Funding/mark: https://www.cryptohftdata.com/datasets/bybit-funding-rate-data  
Known gaps: https://www.cryptohftdata.com/docs/data-gaps-and-corrections

The provider describes an independent hourly Parquet archive beginning 2025-06-28, with Bybit futures L2, tick trades, mark/funding, open interest and other feeds. Its own documentation discloses material limitations:
- Bybit trade files have reconnect gaps from seconds to about three minutes, commonly around 02:00–02:50 UTC; a public-archive backfill is listed as planned.
- Two large missing Bybit hourly ranges are listed: 2025-11-26 10 through 2025-12-26 19 UTC, and 2026-04-13 15 through 2026-04-14 21 UTC.
- Bybit mark-price files before the 2026-09 data-integrity release contain change-only deltas; unchanged fields are null and require correct per-symbol forward filling.
- The provider lists Bybit REST order-book snapshot handling as under review; L2 is aggregate price-level depth, not L3 individual orders or queue priority.
- The listed Bybit families do not include a native OHLCV candle dataset. Trades could be aggregated into bars only with explicit gap and bar-construction controls; this does not solve missing data.

Preliminary fit: possible D7 and partial D2/D3 research input, not a complete strategy-validation package. D1 and D4–D6 are not supplied by the listed families. Provider documentation and sample rows are not a substitute for independent raw-file verification.

**Candidate C — official Bybit public archives and APIs**  
Bybit's public documentation says historical trades can be downloaded from its archive site and documents public market endpoints for klines, mark-price klines, funding history, instruments, and risk limits. The existing AAVE diagnostic used public Bybit trade and quote-saver L2 archives. This is a potential venue-origin source, but it does not remove the historical PIT problem: current instrument/risk endpoints do not reconstruct old effective-time specifications or complete delisted/suspension history. Any future collection remains blocked by the active project hold and is not authorized by this inventory.

**Candidate D — Tardis.dev Bybit Derivatives archive**  
Bybit-specific coverage: https://docs.tardis.dev/historical-data-details/bybit.md  
General data semantics: https://docs.tardis.dev/faq/data.md

The provider documents Bybit derivatives history from 2020-05-28 for linear contracts and 2019-11-07 for inverse contracts. Its Bybit-specific page lists raw WebSocket channels and coverage transitions: legacy `trade` through 2023-04-05 and `publicTrade` from 2023-04-05; L2 order-book channels with several depth/version changes; ticker snapshots/deltas; and an `instrument_info` channel only through 2023-04-05. The provider says the raw messages are sourced from exchange WebSocket feeds and stored with local receive timestamps. Some monthly first-day CSV samples are publicly downloadable without an API key; broader historical replay/API access is subscription-controlled.

Preliminary fit:
- **D1:** potentially strong native trade-event input from which H1 OHLCV can be deterministically aggregated, but the two trade-channel eras, event ordering, symbol coverage and collection gaps must be reconciled. This is not a ready-made accepted OHLCV package.
- **D2/D3:** ticker/derivatives fields may support mark/funding context, but the Bybit-specific channel/schema and event coverage must be verified before treating them as complete mark-price and settlement history. No acceptance from the general provider capability statement alone.
- **D4:** historical recorded symbols and delisted-instrument inclusion are useful, but do not establish every suspension/resumption transition or a complete point-in-time tradability log.
- **D5/D6:** no effective-time instrument-specification or risk-tier history is established by the reviewed Bybit page. The listed `instrument_info` stream ends on 2023-04-05 and cannot alone cover later changes.
- **D7:** strongest current public-documentation lead for execution research: raw Bybit L2 snapshots/deltas and trades, but it is L2 market-by-price rather than L3 order-by-order queue data. Depth/channel versions change over time, so replay rules must be channel-specific.

No Tardis data, samples, or API responses were downloaded or inspected in this screening. The provider is a **candidate for a future provenance/coverage spot-check**, not an accepted source and not a substitute for D4-D6. Its subscription cost and exact symbol/date coverage for the proposed experiment remain unverified.

**Commercial-access check (public pricing page reviewed 2026-11-24):** the listed Bybit Derivatives data-plan tiers show Academic at USD 350/month (quarterly or yearly billing only), Solo at USD 700/month, Professional at USD 1,000/month, and Business at USD 3,000/month. Academic eligibility requires confirmation; the Professional tier adds raw replay/API, Tardis Machine and instrument metadata access, while Academic/Solo are CSV-only. Under the published billing rules, Academic/Solo/Professional yearly subscriptions expose four years of historical data; Business yearly exposes all available history. Therefore the advertised Bybit start date of 2020-05-28 for linear contracts does **not** imply that a normal four-year plan purchased in late 2026 includes the full history back to 2020. Exact quote, tax, data-plan scope and contractual access window would need confirmation directly from the provider before any purchase decision.

**Cost-benefit decision:** do not purchase or trial a paid Tardis plan at this stage. Even the lowest listed derivatives tier is a recurring material cost, and Tardis does not close D4-D6. Its strongest contribution would be D7 execution research and potentially raw trades for D1 bar construction; neither is the currently decisive missing gate for a first defensible strategy test. Reconsider only after a frozen experiment specification proves that tick/L2 data is essential, the required symbol/date sample is known, and a separately authorized data budget exists.

**Additional D4-D6 boundary check from Tardis metadata documentation:** Tardis describes its instrument metadata `changes` history as guaranteed accurate/complete only for `contractMultiplier`; `priceIncrement` and `amountIncrement` changes are best-effort and may be incomplete. Its `availableTo` is the date Tardis stopped collecting and may lag the actual exchange delisting. The API's `active` field is current tradability, not a historical PIT status timeline. This means the metadata API cannot be treated as a complete D4 lifecycle or D5 effective-time specification archive. The instrument metadata API is also restricted to active Pro/Business subscriptions. Bybit's current instrument-info endpoint returns online trading pairs, and its documentation notes that certain quantity-limit fields are adjusted twice monthly; current snapshots therefore support forward-dated evidence capture, not retroactive reconstruction of historical effective values.



### 11.4. Acceptance decision

| Requirement | Current decision after this checkpoint |
|---|---|
| D1 Bybit-native OHLCV | `missing` in repository; Hugging Face lead is `unverified`; Tardis raw trades are a promising but unverified bar-construction input |
| D2 Bybit Mark | `missing/unverified` in repository; external leads, including Tardis ticker fields, remain `unverified` for full historical coverage |
| D3 Funding + settlements | `missing/unverified` in repository; external leads, including Tardis derivative ticker fields, remain `unverified`; settlement completeness not established |
| D4 PIT universe/lifecycle | `missing/unverified`; delisted-symbol inclusion in HF/Tardis does not prove full PIT transitions |
| D5 Effective-time instrument specs | `missing` |
| D6 Effective-time risk tiers | `missing` |
| D7 Representative trades/L2 | `missing`; Tardis is a promising documented lead, but no sample/coverage acceptance has been performed; old AAVE diagnostic is not retained |
| D8 Fee assumptions | `unverified` for dated account/symbol-specific rates; conservative scenario assumptions remain a separate model choice |

**Decision: DATA GATE REMAINS BLOCKED.** No source found in this screening qualifies as a complete, independently verified D1–D6 package for the target market and interval. Combining several unverified providers does not create a verified dataset. These leads do not authorize downloads, account creation, API calls, collectors, runner setup, market-PnL tests, or paper/live execution.

The next allowed action remains read-only documentation/code review. A later data-acceptance exercise requires a separate explicit decision that changes the current data-collection hold; until then, preserve the blocked state and do not manufacture progress through more strategy experiments.




## 12. Static compatibility audit of the existing H1 validation path (2026-11-24)

Read-only inspection of the current research-branch scripts/workflow found:

- `scripts/run_h1_shared_capital_portfolio_validation.py` requires a frozen top-five selection manifest with immutable input/code provenance. It explicitly requires `BYBIT_INSTRUMENT_SPECS_DIR`, `BYBIT_RISK_TIERS_DIR`, `BYBIT_FUNDING_DIR`, `BYBIT_MARK_PRICE_DIR`, and `BYBIT_KLINE_DIR`. The runner's kline resolver states that the signal/execution price source must be official Bybit linear H1 trade-kline CSVs and refuses Binance/CryptoFetch proxy candles.
- Funding acceptance is not just a CSV shape check: each symbol requires its funding audit manifest and validated settlement schedule; mark candles must cover required timestamps; trade-kline, mark and funding coverage must align on the scored folds.
- The current workflow `.github/workflows/h1-shared-capital-portfolio-validation.yml` exposes separate repository paths for Bybit kline, funding and mark-price CSVs and points instrument/risk directories to dated snapshot paths. It derives the exact five-symbol allowlist from the frozen selection manifest.
- `scripts/cryptofetch_sparse_loader.py` is explicitly a local CryptoFetch archive reader; no adapter for the Hugging Face Parquet schema or CryptoHFTData hourly Parquet schema was found in the inspected source set.
- `scripts/archive_bybit_market_history.py` is a venue API collector that requires a Bybit lifecycle snapshot and dated instrument snapshots, then writes archive manifests and per-source files. Its existence does not authorize running it.

**Compatibility conclusion:** neither external discovery lead can be plugged into the current H1 runner as-is. A future use would require a separately reviewed adapter, preservation of original provider files and hashes, field/time-unit mapping, provenance manifest, and all existing D1–D6 gates. In particular, a third-party OHLCV file labelled “Bybit” cannot bypass the runner's native-source and PIT snapshot requirements by being renamed into the expected directory. No adapter, test, collector or PnL run was created or executed in this checkpoint.




## 13. Static boundary audit for D4–D6: what dated snapshots can and cannot prove

Inspected `snapshot_bybit_linear_universe.py`, `snapshot_bybit_instruments.py`, `snapshot_bybit_risk_limits.py`, `instrument_spec_history.py`, and `bybit_risk_tiers.py`. This was source inspection only; collectors and tests were not run.

**D4 — point-in-time universe/lifecycle**
- The universe collector is more complete than a plain current-tickers list: it paginates the default Trading/PendingOpen set and explicitly queries PreLaunch, Settling, Delivering and Closed statuses. It records the full returned instrument rows, `launchTime`, `deliveryTime`, status counts, fetch time and per-page timing/provenance.
- The lifecycle predicate uses contract type, quote/settlement coin, launch time and delivery time. For terminal/in-progress terminal statuses without a positive delivery boundary, it fails closed rather than inventing an end date.
- However, each output is still a **point-in-time observation**, not a historical lifecycle event log. It does not establish every past suspension/resumption interval or prove that Bybit retains every delisted contract indefinitely. A current `Closed` row plus launch/delivery timestamps is not a complete reconstruction of all prior tradability states.
- No dated universe snapshot is currently committed in the repository. D4 remains `partial/unverified`, not accepted.

**D5 — effective-time instrument specifications**
- Instrument snapshots preserve raw Bybit instrument fields, category, fetch time, collection bounds and page observations. `InstrumentSpecHistory.get_spec()` selects only the newest complete snapshot with `fetched_at <= as_of_ts`; it fails if no earlier snapshot exists and can reject a stale snapshot when a maximum age is configured.
- This is a sound forward-observation model once snapshots have begun and are stored immutably. It does **not** infer the effective time of a change between snapshots and cannot recover a specification that changed before the first retained snapshot. A snapshot captured today cannot be applied backward to an earlier fold.
- No dated instrument snapshot series is currently committed. D5 remains `missing` for the historical interval under consideration.

**D6 — effective-time risk tiers**
- Risk-tier snapshots paginate the returned symbol/tier rows, validate tier structure and monotonic relationships, and record fetch time/page provenance. `RiskTierHistory.get_tiers()` и `RiskTierHistory.get_tier()` выбирают последний snapshot не позднее запрошенного timestamp и fail-closed завершаются при отсутствии или устаревании покрытия.
- The same temporal limitation applies: the endpoint snapshot records the observed tier table at capture time, not an authoritative historical effective-time change log. It cannot reconstruct pre-capture tier changes.
- No dated risk-tier snapshot series is currently committed. D6 remains `missing` for the historical interval under consideration.

**Operational implication:** the existing collectors can begin building a forward-dated evidence trail only after an explicit future authorization and successful capture. Their presence in GitHub does not create historical PIT data retroactively. Since the current workflows are manual-only and the user hold prohibits runner setup/dispatch, no new snapshots can be assumed or scheduled in this project state.


## 14. Read-only screening of official announcement history (2026-11-24)

This section records public documentation and web-visible announcement evidence only. **The public announcement API GET was not successfully executed from the research environment; no API response was collected, no announcement archive was downloaded, and no market data or collector was run.** Search-index and Telegram preview results are discovery evidence, not a complete census.

### 14.1. Official V5 announcement API contract

The official documentation for `GET /v5/announcements/index` specifies:
- required `locale`; optional `type`, `tag`, `page`, and `limit`;
- response-level `total` and `list[]`;
- announcement title, description, type key/title, tags, URL, `dateTimestamp`, and `publishTime`;
- no documented date-range filter, so historical coverage would have to be established by pagination and independent boundary checks.

The documentation's static response example contains `total: 735` and an ARB listing dated 2023-03-17. **This is a documentation example, not a current API count and not proof that a live request currently returns all 735 records.** The example timestamp and the documented API launch date must not be conflated with the earliest date actually available from a live query.

A schema inconsistency also needs to be handled defensively: the response-parameter table names `startDataTimestamp`, while the sample response uses `startDateTimestamp`. The field is described as activity-event-specific. Any future parser must preserve raw payloads and tolerate neither name as an assumed universal field without an observed response.

Official reference: https://bybit-exchange.github.io/docs/v5/announcement

### 14.2. Official Telegram channel as a historical discovery index

The public preview of `@Bybit_API_Announcements` is navigable with Telegram's `before` / `after` pagination parameters. The reviewed public pages expose dated messages reaching back to 2019-12-18. This is useful as a second discovery path, but the channel is an API-announcement channel, not a guaranteed complete mirror of every Bybit product/market announcement. It must not be treated as a complete lifecycle database.

Examples found in the channel and linked official announcements:
- March 2023: changes to maximum open interest for perpetual contracts; risk-limit/applicable-leverage changes for STXUSDT, ARBUSDT and MASKUSDT.
- April 2023: risk-limit adjustment for RNDRUSDT and FITFIUSDT; tick-size change for REEFUSDT; maximum-order-size adjustment for RNDRUSDT.
- September 2023: ZBCUSDT Perpetual delisting effective 2023-09-14 07:00 UTC; several spot-pair delistings were scheduled for 2023-09-15.
- January 2024: Bybit announced that `GET /v5/market/instruments-info` for Options would filter out historical `OFFLINE` symbols. This is direct evidence that a current instrument-info response is not a complete historical symbol inventory.
- February 2024: Bybit announced a transition of derivatives risk-limit tiers from manual selection to automatic adjustment based on position value and active orders, with the rollout date later postponed from February 5 to February 20. This is material to D6: a static symbol-level tier table alone may not reproduce the account's effective risk tier.

References:
- Telegram public archive: https://t.me/s/Bybit_API_Announcements
- Historical page around 2019–2020: https://t.me/s/Bybit_API_Announcements?before=25
- Historical page around 2023: https://t.me/s/Bybit_API_Announcements?after=113
- Delisting example: https://t.me/s/Bybit_API_Announcements?before=165
- Risk-tier automation announcement: https://t.me/s/Bybit_API_Announcements?before=207

### 14.3. What this does and does not establish for D4–D6

| Gate | New evidence | Acceptance effect |
|---|---|---|
| D4 — PIT universe/lifecycle | Official delisting notices and dated API-channel references exist; the current instrument-info endpoint was explicitly changed to omit historical OFFLINE Options symbols | Improves discovery of individual listing/delisting events, but does not establish complete listing, suspension, resumption, or delisting coverage for every linear contract. Remains `partial/unverified`. |
| D5 — effective-time specs | Dated tick-size, maximum-order-size, and listing announcements exist | Can recover selected parameter changes when the announcement includes the old/new values and effective time. Does not provide a complete continuous history of all tick/qty/minimum-notional/contract fields. Remains `missing` for full-interval acceptance. |
| D6 — risk tiers | Dated risk-limit/leverage announcements exist, including 2023 adjustments and the 2024 move to automatic tier adjustment | Useful event evidence, but does not establish a complete historical tier table or account-specific effective tier for every position/order state. Remains `missing` for full-interval acceptance. |

The public announcement API and Telegram archive are therefore **promising supplemental evidence sources**, not a substitute for the dated PIT snapshots and complete effective-time records required by D4–D6. A future acceptance exercise would need to enumerate every relevant page/message, retain original bodies and URLs, normalize publication and effective timestamps separately, reconcile corrections/postponements, and compare the recovered event history with independent Bybit snapshots or exports.

### 14.4. Current decision

- Announcement discovery has materially improved: there is a documented public API contract, a paginated official API-announcement channel with historical messages, and public examples of relevant delisting/specification/risk events.
- The live API's current `total`, earliest returned record, page-depth behavior, locale coverage, deletion/retention policy, and completeness remain **unverified** because no successful GET response was obtained.
- Search-engine results and Telegram preview pages are not a complete machine-readable event archive; they may omit posts, expose only excerpts, or change as the platform updates.
- D4 remains `partial/unverified`; D5 and D6 remain `missing` for the required full historical interval.
- **DATA GATE REMAINS BLOCKED.** This screening does not authorize API collectors, market-data downloads, runner setup, market-PnL tests, or paper/live execution.


## 15. Additional historical channel evidence and completeness counterexamples (2026-11-24)

This is a further read-only review of public Telegram previews and current official Help Center rules. It is not a bulk archive, API response, or exhaustive event census.

### 15.1. Historical evidence from the main Bybit announcement channel

The main public `@Bybit_Announcements` channel exposes dated derivatives lifecycle and risk notices from 2022, separate from the API-focused `@Bybit_API_Announcements` channel.

Examples visible in public previews:
- 2022-05-12: LUNAUSDT Perpetual delisting notice describes the price-triggered mechanism; the later notice says the contract was settled/delisted at 10:03 UTC after the index price reached the trigger.
- 2022-05-13: USTUSDT Perpetual delisting at 01:30 UTC, with active/conditional orders cancelled and open positions closed using the best available price with taker fee.
- 2022-05-13: ANCUSDT Perpetual delisting at 03:45 UTC.
- 2022-07-21: GSTUSDT Perpetual delisting at 08:00 UTC.
- A 2022 derivatives risk-limit adjustment notice names AAVEUSDT, FILUSDT, RUNEUSDT, CHZUSDT and IOSTUSDT.

These are useful dated event records, but public Telegram search previews do not establish that every historical message is indexed or that all notices are retained.

References:
- Main Bybit announcements around May 2022: https://t.me/s/Bybit_Announcements?before=1013
- GSTUSDT delisting context: https://t.me/s/Bybit_Announcements?before=1256

### 15.2. A direct counterexample to announcement-only lifecycle reconstruction

The official Derivatives Delisting Mechanism states that Bybit may delist a derivatives contract without further notice when its last traded price falls below 20 times the minimum price precision (tick size). It also describes an earlier notification threshold at 50 times tick size.

This means a complete lifecycle history cannot be reconstructed from scheduled delisting announcements alone: the exchange's published rules explicitly allow some delistings without a prior announcement. The LUNAUSDT May 2022 notices illustrate a price-triggered emergency case, but they do not prove every such event was documented in the same way.

Official rule: https://www.bybit.com/en/help-center/article/Bybit-Derivatives-Delisting-Mechanism-DDM

**D4 consequence:** event announcements are supplemental evidence only. To accept a historical universe, we need an authoritative source that captures actual status transitions (including unexpected suspension/delisting) or a defensible reconciliation of dated snapshots with independently verified event logs. A list of announced delistings cannot satisfy this requirement.

### 15.3. D6 is account-state dependent, not just a symbol table

The current official Risk Limit help article describes automatic tier adjustment based on the value of open positions and active orders, with the mark price affecting position/order value. It also distinguishes One-Way and Hedge calculations and excludes Reduce Only / Close on Trigger orders from the effective position value.

The article further states that exchange-wide risk-parameter changes can affect IMR, MMR, maximum leverage and position limits, and may be applied immediately or after a 10-day buffer depending on account risk.

Official rule: https://www.bybit.com/en/help-center/article/Risk-Limit-Perpetual-and-Expiry-Contracts

**D6 consequence:** dated instrument risk-tier snapshots alone are not enough to reproduce an account's effective tier. A historically faithful model would need, at minimum, the applicable tier schedule and rules version, mark-price inputs, position and active-order state, position mode, leverage setting, and the timing/eligibility of parameter changes. Account-specific margin mode and any buffer/restriction state are additional variables. The current help article documents today's rule description; it does not establish when every clause became effective historically.

### 15.4. API-channel chronology: useful for discovery, not a market-event ledger

The public API-announcement preview shows:
- 2019-12-27: initial Set Risk Limit and Get Risk Limit List endpoints;
- 2021-02-01: an API changelog says Tiered Margin was upgraded to Risk Limit and adds Set Risk Limit;
- 2021-03-18: Get Risk Limit response added `max_leverage`;
- 2021-06-28: the inverse Query Symbol endpoint corrected `min_price` and `tick_size` for BCHUSDT and UNIUSDT;
- 2021-06-29: new USDT perpetual symbols were added;
- 2022-03-01: Query Symbol added `funding_interval`;
- 2022-04-29: maximum PostOnly trading quantity was increased, with the value exposed through Query Symbol;
- a later API notice says the V5 Get Risk Limit endpoint's page size would change from 30 to 15, requiring cursor pagination.

These entries show that API schemas and available fields changed over time. They do not provide the underlying historical values for every symbol and date. In particular, a changelog that says a field was added or corrected is not a historical specification snapshot.

References:
- API channel early history: https://t.me/s/Bybit_API_Announcements?before=25
- 2021 API history: https://t.me/s/Bybit_API_Announcements?before=85
- 2022 API history: https://t.me/s/Bybit_API_Announcements?before=102
- Risk-limit pagination notice: https://t.me/s/bybit_api_announcements?before=306

### 15.5. Updated decision

- D4: official channel evidence confirms selected scheduled and emergency delisting events, while the official rule confirms that delisting can occur without further notice. Announcement-only reconstruction is structurally incomplete. Status remains `partial/unverified`.
- D5: API changelogs reveal schema evolution and selected historical field corrections, but do not reconstruct full effective-time instrument specifications. Status remains `missing`.
- D6: risk-limit rules are dynamic and account-state dependent; a static dated tier table is insufficient by itself. Status remains `missing`.
- The public API GET is still not verified by a live response; no total count, oldest returned record, or complete pagination depth is known.
- No new market-data archive, collector, runner, market-PnL test, paper trade, or live trade was run.
- **DATA GATE REMAINS BLOCKED.** The next legitimate improvement is source-level acceptance design for actual lifecycle and account-state records, not more isolated announcement examples.


## 16. V5 API changelog audit: dated schema evolution and current-endpoint limitations (2026-11-24)

This section is based on the official V5 API documentation and changelog. It is documentary evidence, not a live API response or historical data download.

### 16.1. Instrument specifications are not static

The official `Get Instruments Info` documentation states that:
- `maxLimitOrderQty`, `maxMarketOrderQty`, and `postOnlyMaxLimitOrderSize` are adjusted twice monthly, on the 3rd and 17th at 08:00 UTC+8; users must not assume they remain constant.
- `linear` and `inverse` default status responses return `Trading` and `PendingOpen`; other lifecycle states require explicit status queries.
- `launchTime` and `deliveryTime` are returned, with `deliveryTime` also used as perpetual delisting time.
- Current responses include tick size, quantity step, minimum notional, max order quantities, leverage limits, funding interval and funding-rate bounds.

Official reference: https://bybit-exchange.github.io/docs/v5/market/instrument

The official V5 changelog documents that fields were added at different dates, rather than being available throughout the entire API history:
- 2023-04-06: `status` filter added to Get Instruments Info.
- 2024-01-18: `riskParameters`, `limitParameter`, and `marketParameter` added.
- 2024-02-06: `upperFundingRate` and `lowerFundingRate` added.
- 2024-02-21: `maxMktOrderQty` added and `postOnlyMaxOrderQty` superseded by `maxOrderQty`.
- 2024-04-11: `minNotionalValue` added.
- 2024-06-27: status filtering expanded to `Closed`, `Delivering`, and `PreLaunch` for linear/inverse.
- 2026-09-01: `PendingOpen` status added for futures.
- 2026-09-29: `tags` field added for linear/inverse.

Official reference: https://bybit-exchange.github.io/docs/changelog/v5

**D5 consequence:** the present response schema cannot be projected backwards as though every field existed in 2020–2023. A historical specification model needs field-level availability dates, effective dates of values, and explicit unknowns before a field was introduced. The twice-monthly quantity-limit changes are a direct reason that one current snapshot cannot represent historical order constraints.

### 16.2. Risk-limit API history has structural breaks

The official V5 changelog records:
- 2024-03-12: `Set Risk Limit` deprecated because automatic risk limit had launched.
- 2024-04-30: `Get Risk Limit` began returning 30 linear symbols per request and added `nextPageCursor`.
- 2024-08-26: page size changed from 30 to 15.
- 2025-08-28: Get Risk Limit added support for pre-market contract risk-limit tables.

Official reference: https://bybit-exchange.github.io/docs/changelog/v5

These changes create at least three historical API regimes: before automatic risk-limit operation, the initial automatic-risk period, and later cursor-paginated response behavior. A collector that assumes today's pagination or today's automatic tier semantics for older dates would be incorrect.

### 16.3. Current risk rules include account-state and transition behavior

The current official Help Center article states that:
- risk tier is adjusted automatically from open position value and active-order value;
- for USDT/USDC contracts, position/order value uses contract size multiplied by mark price;
- Reduce Only and Close on Trigger orders are excluded from effective position value;
- One-Way and Hedge modes are handled by side;
- mark-price changes can change the tier in real time;
- platform-wide risk-parameter changes can be applied immediately when account risk is low, or can trigger a 10-day buffer with restrictions when risk is high.

Official reference: https://www.bybit.com/en/help-center/article/Risk-Limit-Perpetual-and-Expiry-Contracts

**D6 consequence:** reconstructing effective risk constraints requires more than a historical per-symbol tier table. It needs the rules version and effective time, dated tier schedule, mark price, open position and active-order state, order flags, position mode, and any account-specific transition/buffer state. The current Help Center page does not prove that every current rule applied unchanged in earlier years.

### 16.4. Updated acceptance decision

- D4: unchanged — announcement-only reconstruction cannot guarantee complete lifecycle coverage; automatic delisting may occur without prior notice.
- D5: strengthened negative evidence — the official API itself confirms recurring quantity-limit changes and multiple schema additions over time. Dated field-level snapshots remain necessary. Status: `missing` for full historical acceptance.
- D6: strengthened negative evidence — official changelog establishes the transition to automatic risk limits and later API pagination changes; current rules show account-state-dependent tier application. Status: `missing` for full historical acceptance.
- No live API response, current API count, archive, market data, collector, runner, PnL run, paper order, or live order was produced by this audit.
- **DATA GATE REMAINS BLOCKED.**


## 17. Risk-limit endpoint cannot serve as a historical tier database

A focused check of the current official `GET /v5/market/risk-limit` reference shows that the response exposes the current tier rows (`riskLimitValue`, `maintenanceMargin`, `initialMargin`, `maxLeverage`, `mmDeduction`, etc.) and a pagination cursor, but no effective-from/effective-to timestamps or historical query parameters.

The official changelog documents these API changes:
- 2023-10-25: `Get Position Info` added `isReduceOnly`, `mmrSysUpdatedTime`, and `leverageSysUpdatedTime`; a `Confirm New Risk Limit` endpoint was added.
- 2024-03-12: `Set Risk Limit` was deprecated because automatic risk limit had launched.
- 2024-05-09: `Get Risk Limit` added cursor pagination and returned 30 linear symbols per page.
- 2024-12-12: linear page size changed from 30 to 15.
- 2025-08-28: support for pre-market risk-limit tables was added.

Official references:
- https://bybit-exchange.github.io/docs/v5/market/risk-limit
- https://bybit-exchange.github.io/docs/changelog/v5

**D6 consequence:** the public risk-limit endpoint is a current-state lookup, not a time-series endpoint. Its cursor only traverses the current response set; it does not page through historical effective dates. The timestamps added to Position Info are account/position fields, not a public historical risk-tier archive, and they appeared only in October 2023. They cannot fill earlier history or replace periodic snapshots. Historical tier reconstruction therefore requires independently retained dated responses or a verifiable exchange event archive plus the exact rules in force at each time.

Acceptance remains `missing` for D6. No private account API was accessed or requested, and no live response from the risk-limit endpoint was collected in this audit.


## 18. Important qualification: historical-time parameters once documented for Get Instruments Info (2023-04-04)

A closer reading of the official V5 changelog reveals an item not covered by the current endpoint reference:

- On 2023-04-04, the changelog says **Get Instruments Info added request parameters `startTime` and `endTime`, effective for UTA mode**.
- The current official Get Instruments Info reference and current API Explorer request schema list `category`, `symbol`, `symbolType`, `status`, `baseCoin`, `limit`, and `cursor`, but do not list `startTime` or `endTime`.
- The current response still describes instrument specifications for online trading pairs and includes launch/delivery timestamps, but does not document an effective-dated history response contract.

Official references:
- Changelog: https://bybit-exchange.github.io/docs/changelog/v5
- Current endpoint reference: https://bybit-exchange.github.io/docs/v5/market/instrument
- Current API Explorer schema: https://bybit-exchange.github.io/docs/api-explorer/v5/market/instrument

### Interpretation and required follow-up

This is a material unresolved lead for D4/D5, not evidence that historical specifications are available:
1. The 2023 changelog establishes that time parameters were documented for this endpoint at that date and under a UTA-mode qualification.
2. The changelog does not define whether the parameters queried historical instrument state, filtered account-instrument records by time, or had another limited meaning.
3. The current endpoint reference and API Explorer omit those parameters. We have not established when or why they disappeared, whether the behavior remains accepted by the server, what date range/retention exists, or whether results include historical values rather than current records.
4. No API request was made as part of this documentary audit. In particular, the prior permission for anonymous public GET access was limited to the announcements endpoint; it does not authorize probing the instruments endpoint.

**Correction to Section 16:** do not treat the current reference's lack of time parameters as proof that Bybit never offered historical instrument queries. Equally, do not treat the 2023 changelog line as proof of a usable, complete historical metadata archive. D5 remains `missing / unresolved historical-query lead` until official semantics, current support, historical depth, and field coverage are independently established. D4 remains partial/unverified.

A bounded next documentary task is to recover the 2023-04-04 API schema/PR history and determine the exact meaning and removal date of `startTime`/`endTime`. If that cannot be established from public documentation history, the next step requires explicit permission for a read-only public GET against the instruments-info endpoint; it must not be silently tested under the announcements-only authorization.


## 19. Git-history cross-check of the 2023 instrument-time-parameter lead

The public `bybit-exchange/docs` repository was checked read-only to avoid interpreting a changelog line in isolation.

- The historical `docs/v5/market/instrument.mdx` file at commit `8cce6d002d126ad9a48c0584a317c37ce17ba6ce` (2023-03-09) documents category, symbol, baseCoin, limit and cursor; it does not document `startTime` or `endTime`.
- The current file at the repository's `master` ref also omits `startTime` and `endTime`.
- A broad GitHub search for the terms `startTime` and `endTime` surfaced PR #245 (December 2023), but its actual commit patch changes documentation for closed PnL, executions, transaction logs, and order history; it does **not** touch Get Instruments Info. This is a verified false positive and must not be cited as evidence for instrument-history support.
- The official V5 changelog still contains the 2023-04-04 line attributing `startTime`/`endTime` to Get Instruments Info for UTA mode, but the corresponding API-doc change/PR and precise semantics have not yet been located.

References:
- Historical instrument schema commit: https://github.com/bybit-exchange/docs/commit/8cce6d002d126ad9a48c0584a317c37ce17ba6ce
- Current instrument schema: https://github.com/bybit-exchange/docs/blob/master/docs/v5/market/instrument.mdx
- False-positive PR #245: https://github.com/bybit-exchange/docs/pull/245
- Changelog: https://bybit-exchange.github.io/docs/changelog/v5

**Conclusion:** the 2023 changelog line is an unresolved documentation anomaly, not a verified historical metadata endpoint. The historical instrument-info query hypothesis remains unproven. Do not use it to accept D4 or D5, and do not claim the endpoint never had such parameters. Resolving this requires locating the exact historical API implementation/announcement or receiving explicit authorization for a narrowly scoped public GET test of the instruments-info endpoint.


## 20. Correction: the 2023-04-04 startTime/endTime changelog item is NOT for Get Instruments Info

**Sections 18 and 19 contain a source-attribution error and must not be used as evidence for D4/D5.** The official V5 changelog source was reopened at the historical repository commit `3c9259f42468544ecad1aa7149ffdd111e0a61fe`, which contains the actual 2023-04-04 entry. It explicitly says:

- `Get Order History` [UPDATE]
  - add request param `startTime` `endTime`, effective for UTA mode
  - add response param `placeType`, used for option

The entry does **not** mention `Get Instruments Info`. The earlier attribution to instrument metadata was a misread of the changelog and is withdrawn.

The later Git-history results are consistent with this correction:
- Historical changelog file at the April 4, 2023 repository commit: https://github.com/bybit-exchange/docs/blob/3c9259f42468544ecad1aa7149ffdd111e0a61fe/docs/changelog/v5.mdx
- The December 4, 2023 commit titled `startTime and endTime` (PR #245) changes time-range descriptions for closed PnL, executions, transaction logs, and order history; it does not change Get Instruments Info: https://github.com/bybit-exchange/docs/commit/72510bd779bec629f36faacab44db83fdb7936be
- The February 29, 2024 changelog addition of two-year retrieval windows applies to borrow history, delivery records, and USDC settlement records, not instrument specifications: https://github.com/bybit-exchange/docs/commit/b42fcf16e647cc305b98f87e1f845a4e9d257a9c

### Corrected conclusion

1. There is no verified evidence in the examined official changelog or repository history that Get Instruments Info ever supported historical `startTime`/`endTime` queries.
2. The historical instrument schema at commit `8cce6d002d126ad9a48c0584a317c37ce17ba6ce` and the current schema both omit those parameters. This is consistent with, but does not prove every historical server behavior.
3. The prior proposed historical-query lead for D5 is closed as a false lead. No instruments-info GET was made; no new API permission is needed to close this documentation question.
4. D5 remains `missing` for full historical acceptance. D4 remains `partial/unverified`. The existing independent evidence about recurring quantity-limit changes, schema evolution, and lifecycle gaps remains valid.
5. **DATA GATE REMAINS BLOCKED.**

This correction supersedes the factual claim and proposed follow-up in Sections 18 and 19. Those sections are retained only as an audit trail of the mistaken hypothesis and its falsification.
