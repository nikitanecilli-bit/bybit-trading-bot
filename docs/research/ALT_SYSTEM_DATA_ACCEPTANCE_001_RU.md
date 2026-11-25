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


## 21. New Get Instrument Summary endpoint does not provide historical specifications

The official V5 changelog and repository history establish that `GET /v5/market/instrument-summary` was added on 2026-10-14:
- Changelog entry: new endpoint for summary information and trading increments for linear and option instruments.
- The documented request supports category, symbol, symbolType, marketRegion, baseCoin, limit and cursor.
- The documented response includes identity/display fields, `qtyStep`, `tickSize`, and `deliveryTime`; it does not expose effective-from/effective-to timestamps or historical query parameters.
- The endpoint covers linear and option only, not the full spot/inverse scope of Get Instruments Info.
- It is a separate current summary endpoint, not a documented historical archive.

Repository evidence:
- Introduction commit: `13dce66147ff4bd200fdc6d20176186724a0f7a1` (2026-10-14), which adds the changelog entry and endpoint page.
- Official endpoint reference: https://bybit-exchange.github.io/docs/v5/market/instrument-summary
- Official changelog: https://bybit-exchange.github.io/docs/changelog/v5

**D5 consequence:** this endpoint may be useful for current symbol discovery and current tick/quantity-step checks, but it does not reconstruct historical tickSize/qtyStep or the broader historical fields required by the validation engine. Its introduction in October 2026 also makes it irrelevant as a direct historical source for earlier years unless Bybit separately documents retention/history semantics. No such semantics are documented in the examined endpoint contract.

A third-party Bybit data-source note independently describes current instrument specs as coming from the REST instruments-info/risk-limit endpoints and says delisted symbols are not served by those current lookups. This is corroborative only, not an official completeness guarantee: https://github-wiki-see.page/m/sbOogway/sbt2/wiki/Source-Bybit

**Updated D5 status:** `missing` for full historical acceptance. The new summary endpoint is not a historical-data solution. No API call was made.


## 22. `status=Closed` is a possible current lifecycle inventory, not proven historical completeness

The official V5 changelog records that on 2024-06-27 the Get Instruments Info endpoint expanded its `status` filter to support `Closed`, `Delivering`, and `PreLaunch` for `linear` and `inverse` categories. The current reference/API Explorer lists `Closed` as an allowed status and returns `launchTime`, `deliveryTime`, and instrument fields in the response.

Official references:
- 2024-06-27 changelog: https://bybit-exchange.github.io/docs/changelog/v5
- Current endpoint reference: https://bybit-exchange.github.io/docs/v5/market/instrument
- API Explorer schema: https://bybit-exchange.github.io/docs/api-explorer/v5/market/instrument

### What this could provide

A read-only request using `category=linear&status=Closed` (and separately inverse) may expose the exchange's currently retained closed-contract records, potentially including their launch/delivery times and current returned metadata. This is a plausible source for a partial delisted-symbol inventory and worth testing if explicitly authorized.

### What documentation does not establish

- No documented retention period or earliest historical date for Closed records.
- No guarantee that every delisted/closed symbol since exchange launch remains queryable.
- No documented effective-dated history for tick size, qty step, min notional, max quantities, leverage limits or risk tiers.
- No documented guarantee that emergency delistings, pre-market failures, migrations/renames or all historical status transitions are represented as a complete event log.
- The feature was documented in June 2024; this does not establish that the endpoint exposed the same closed-state query before that date.

**D4 assessment:** this is a potentially useful source for a present-day closed-symbol census, but it cannot yet satisfy point-in-time universe reconstruction. Treat its coverage as unknown until an authorized query can be tested against a separately compiled list of known delistings and dated notices. Announcements remain an incomplete event source because the DDM permits delisting without further notice in specified circumstances.

**D5 assessment:** even if Closed records are returned, one current response cannot reconstruct the historical sequence of mutable specification values. D5 remains `missing`.

No request was made to `/v5/market/instruments-info`; existing permission remains limited to the public announcements endpoint. No market data, collector, archive, runner, PnL or execution action was performed.


## 23. Bybit public trade-archive directory index: verified historical symbol evidence, not a complete lifecycle ledger

A read-only inspection of the public Bybit archive directory index at `https://public.bybit.com/trading/` revealed that the archive retains directories for several historically delisted contracts. This is stronger evidence of historical symbol presence than a search-engine result or a third-party symbol list.

Direct directory listings inspected (filenames only; no archive files were downloaded):
- `ANCUSDT`: daily files from 2022-03-15 through 2022-05-13, plus an isolated `2022-12-12` filename. Directory: https://public.bybit.com/trading/ANCUSDT/
- `USTUSDT`: files dated 2022-05-10 through 2022-05-13, plus an isolated `2022-12-12` filename. Directory: https://public.bybit.com/trading/USTUSDT/
- `LUNAUSDT`: files dated 2021-10-11 through 2022-05-12, plus an isolated `2022-12-12` filename. Directory: https://public.bybit.com/trading/LUNAUSDT/
- `CANTOUSDT`: daily files from 2024-05-23 through 2024-08-12. Directory: https://public.bybit.com/trading/CANTOUSDT/
- The parent index itself currently lists these symbol directories, including ANCUSDT, LUNAUSDT, USTUSDT and CANTOUSDT: https://public.bybit.com/trading/

The ANC and UST directory date spans align with the known May 2022 delisting notices already documented in Sections 14–15. LUNA's last contiguous daily filename is 2022-05-12, also aligned with the known emergency delisting window. These are useful cross-checks between the exchange-hosted trade archive and announcement evidence.

### Important limits and anomalies

1. A directory proves that the archive exposes files associated with a symbol and dates; it does not by itself prove every file is non-empty, complete, or contains a trade at the filename's date. File contents and row-level timestamps were not downloaded or inspected.
2. The isolated `2022-12-12` filename in the ANC, UST and LUNA directories is an anomaly. It must not be interpreted as evidence that trading resumed, that the contract was relisted, or that this was the final trade. It requires row-level inspection and independent event context.
3. A last daily filename is not an exact delisting timestamp. At best, after validating the file contents, it can bound the last observed trade date. The exchange may stop trading intraday; an empty/partial file or archive correction can also distort the apparent boundary.
4. No published retention policy, completeness guarantee, immutable manifest, or historical symbol-universe coverage statement was found for the directory index. The absence of a directory/file cannot be treated as proof that a symbol never traded or was not listed.
5. The public index appears to be a current directory view, not a dated snapshot of what the index contained at every historical point. It cannot independently reconstruct point-in-time membership without archived snapshots or a complete symbol-event source.
6. The index and files are a trade-history source, not an instrument-specification source. They do not supply historical tick size, qty step, min notional, leverage/risk tiers, or other effective-dated constraints.

### D4 assessment update

The public Bybit trade archive is now a **verified supplementary source for historical symbol-presence evidence** and a useful cross-check against notices. It may support a partial historical universe after a separately authorized and validated metadata/indexing step. It does not close D4 because it lacks a proven complete universe, explicit lifecycle events, reliable exact transition timestamps, and a documented retention/completeness guarantee.

### Permission boundary

This audit inspected only public directory-index pages and their visible filenames. It did not download any `.csv.gz` market archive, fetch trade rows, create a local archive, or run a collector. No new permission is implied. The existing no-market-archive/no-collector restriction remains in force.


## 24. Official API documentation explicitly points to the public trade archive

The official V5 `Get Recent Public Trades` documentation states that archived historical trades can be downloaded from the website. The endpoint itself returns only recent public trades (with a bounded `limit`), while the website archive is the separate historical source.

Official reference: https://bybit-exchange.github.io/docs/v5/market/recent-trade

This establishes that `public.bybit.com` is not merely an undocumented third-party mirror: Bybit's own API documentation points users to its website for archived historical trades. The direct `/trading/` directory and symbol subdirectories inspected in Section 23 are hosted on that public archive domain.

This strengthens provenance for historical **trade-presence evidence**, but does not add an instrument metadata or lifecycle completeness guarantee. The API documentation does not state:
- that every historically listed instrument is retained indefinitely;
- that every day/file is complete or non-empty;
- that archive directory names constitute the authoritative point-in-time universe;
- that the final file date equals the exact trading suspension/delisting timestamp.

### Revised D4 source hierarchy

For future, separately authorized validation, the evidence should be combined with distinct roles rather than treated as interchangeable:

1. **Official dated delisting/listing notices and exchange rule notices** — event timing and stated operational treatment, but incomplete by themselves because emergency delisting can occur without further notice.
2. **Bybit public trade archive directory and row-level trade timestamps** — positive evidence that a symbol had executions on observed dates; potential lower/upper bounds around activity, after file integrity and row-level validation.
3. **Dated snapshots of instrument status and specs** — direct point-in-time state evidence, but only from the date snapshots begin; not yet available for the full target interval.
4. **Independent historical market listings / vendor metadata** — corroboration and discrepancy detection only, never silently promoted to exchange-authoritative truth.

No absence-based inference should be made from missing archive files or missing announcements. A valid point-in-time universe requires a reconciliation process that preserves `observed active`, `observed inactive/closed`, and `unknown` as separate states, with source and confidence attached to each symbol/time interval.

**Acceptance remains D4 partial/unverified.** The public archive materially improves the evidence path, but its completeness and row-level quality have not been validated. No market archive file was downloaded.


## 25. Tardis Bybit `instrument_info` capture: a bounded historical lifecycle lead, not a specification archive

The current Tardis Bybit Derivatives coverage page provides a more precise finding than the earlier general vendor assessment:

- Tardis states Bybit inverse-contract historical data is available from 2019-11-07 and linear-contract data from 2020-05-28.
- The legacy Bybit WebSocket channel `instrument_info` is listed as available **until 2023-04-05**, described as “instrument ticker and contract state updates”.
- From 2023-04-05 onward, Tardis lists newer channels such as `publicTrade`, `tickers`, and order-book feeds, but does not list a replacement channel explicitly described as a contract-state/instrument-spec update stream.
- Tardis downloadable CSV data types list trades, order books, quotes, derivative tickers and other datasets, but do not list `instrument_info` as a normalized downloadable CSV dataset. The raw channel is documented as accessible through the historical replay/API path.

References:
- Bybit coverage and channel dates: https://docs.tardis.dev/historical-data-details/bybit
- Tardis downloadable CSV data types: https://docs.tardis.dev/downloadable-csv-files/data-types
- Tardis API access: https://docs.tardis.dev/api/http-api-reference
- Tardis instruments metadata limitations: https://docs.tardis.dev/api/instruments-metadata-api

### Potential value for D4

The old `instrument_info` stream may provide timestamped state updates for the 2020-11/2020-05 through 2023-04 period, depending on contract category and actual per-symbol capture coverage. This is a concrete lead for reconstructing part of the historical lifecycle and could be stronger than announcement-only evidence.

However:
- the documentation's channel description does not itself prove that every status transition or every symbol was captured without gaps;
- the page does not provide a point-in-time completeness guarantee for the instrument-state channel;
- the raw channel schema and event semantics must be validated against Bybit's legacy WebSocket protocol and known lifecycle cases;
- no equivalent explicit state-update channel is documented after 2023-04-05 in this coverage page.

**D4 assessment:** Tardis `instrument_info` is a potentially valuable, bounded historical source through 2023-04-05. It could strengthen D4 for covered symbols and intervals if completeness is tested. It cannot by itself establish a complete lifecycle ledger through the present.

### Why it does not close D5 or D6

- The channel is described as instrument ticker and contract state updates, not as a full historical copy of `instruments-info` or `risk-limit` REST responses. Do not assume it contains tick size, quantity step, minimum notional, order limits, leverage filters, or risk tiers.
- Tardis's separate Instruments Metadata API states that only `contractMultiplier` changes are guaranteed accurate and complete; `priceIncrement` and `amountIncrement` are best-effort. Its `availableTo` can lag actual delisting. This remains insufficient for strict D5 acceptance.
- No documented historical risk-limit tier archive or account-state history is provided by the examined Tardis Bybit coverage.

**D5 remains missing. D6 remains missing.**

### Cost and permission decision

Tardis's raw historical replay/API route is not equivalent to its public monthly sample CSVs. The downloadable CSV schema does not include `instrument_info`; access path, exact symbol coverage, retention, and price must be confirmed before any purchase. No subscription should be purchased at this stage.

This audit was documentation-only. No Tardis API request, download, account connection, subscription, collector, or market-data archive was used.


## 26. CoinAPI historical-symbol metadata: a stronger D4 candidate, but not an exchange-rules archive

CoinAPI documents a dedicated endpoint `GET /v1/symbols/{exchange_id}/history` that returns symbols no longer actively traded/listed on an exchange, with pagination. Its FAQ explicitly says it retains historical/inactive symbols when the symbol was supported at introduction, and points to this endpoint for delisted-symbol discovery.

CoinAPI also documents Bybit integration for perpetual/futures data and gives `BYBIT` as an exchange identifier in its perpetual-symbol examples. This makes CoinAPI a concrete vendor candidate for D4 rather than a generic possibility.

References:
- Historical symbols endpoint: https://www.coinapi.io/products/market-data-api/docs/rest-api/metadata/symbols/exchange_id/history/get
- CoinAPI data coverage FAQ: https://www.coinapi.io/products/market-data-api/faq
- Bybit integration page: https://www.coinapi.io/products/market-data-api/exchanges/bybit
- Symbol metadata overview: https://www.coinapi.io/datasets/asset-and-symbol-metadata

### Potential D4 value

The endpoint's stated purpose directly matches the missing historical inactive/delisted symbol inventory. Its symbol records can include:
- exchange-native symbol mapping;
- instrument type and base/quote assets;
- market-data coverage start/end dates, including trade/quote/order-book intervals where available;
- normalized precision fields.

This could provide a second independently maintained symbol universe against which Bybit's own trade archive and announcements can be reconciled. It is particularly useful for discovering symbols that no longer appear in Bybit's current REST instrument list.

### Limits and acceptance risks

1. CoinAPI's retention statement is conditional: a symbol must have been supported by CoinAPI when introduced. It is not a guarantee that every Bybit listing is present.
2. The documentation confirms Bybit integration, but we have not yet verified the exact exchange identifier(s), derivative-category split, or returned history coverage for the target period by a live metadata response.
3. `data_trade_start/end`, `data_quote_start/end`, and `data_orderbook_start/end` describe CoinAPI's own data coverage, not the exact Bybit listing/delisting timestamps.
4. CoinAPI explicitly warns that `price_precision` and `size_precision` are not necessarily the exchange's actual trading increments; these values can be derived after the fact and may lag changes. They are not substitutes for historical `tickSize`, `qtyStep`, min notional, order limits, or risk tiers.
5. No historical effective-dated risk-limit schedule or account-state reconstruction is documented by this symbol metadata endpoint.

### Updated gap assessment

- **D4:** CoinAPI historical symbols is a promising candidate to test for universe completeness, in addition to the Bybit public trade archive and dated notices. It does not yet close D4 because actual Bybit response coverage, known-delisting recall, and symbol-history semantics have not been verified.
- **D5:** remains missing. CoinAPI precision fields are not guaranteed exchange trading rules and are not documented as a complete effective-dated spec history.
- **D6:** remains missing. No risk-limit tier history or account-state-dependent rules archive is established.

### Next bounded evaluation (no purchase or data download)

If a free trial or sample metadata response is available, the acceptance test should be metadata-only:
1. Confirm Bybit's exact exchange identifier(s) for linear and inverse derivatives.
2. Request active and historical symbol lists with pagination.
3. Check whether known cases already identified in this audit (LUNAUSDT, USTUSDT, ANCUSDT, and other dated delistings) are present with plausible data coverage intervals.
4. Compare the returned symbol set with the public Bybit trade-archive directory and official notices; quantify matches, omissions, duplicate/renamed instruments, and unexplained records.
5. Reject any claim of completeness unless the vendor states coverage scope and the known-case reconciliation passes.

No CoinAPI API request, API-key creation, paid trial, market-data download, or subscription was made. This is a vendor-evaluation lead only.


## 27. CoinAPI Bybit identifiers and access gate: metadata-only test is defined, but cannot yet be executed

A closer check of CoinAPI's current public documentation resolves part of the identifier ambiguity:

- CoinAPI's Bybit integration page explicitly uses `exchange_id=BYBIT` and documents perpetual/futures coverage under the Bybit integration.
- CoinAPI's FAQ separately lists `BYBIT`, `BYBITINVERSE`, and `BYBITUSDC` as distinct exchange identifiers for funding-rate coverage. This is strong evidence that the metadata test must not assume one identifier covers every derivatives category.
- The historical-symbol endpoint is `GET /v1/symbols/{exchange_id}/history`, paginated by `page` and `limit`; it requires an API key in the Authorization header (or an accepted API-key header). The public documentation's response example is for Kraken and is not evidence of Bybit symbol coverage.
- CoinAPI's FAQ says inactive/delisted symbols are retained only if CoinAPI supported the symbol when it was introduced. The same FAQ says metadata does not guarantee that every dataset is available for every symbol.

References:
- Bybit integration and `BYBIT` example: https://www.coinapi.io/products/market-data-api/exchanges/bybit
- Funding coverage exchange IDs: https://www.coinapi.io/products/market-data-api/faq
- Historical-symbol endpoint and authentication: https://www.coinapi.io/products/market-data-api/docs/rest-api/metadata/symbols/exchange_id/history/get

### Consequence for the proposed known-case test

The minimum useful metadata-only test, if an already-authorized API key or vendor-provided sample becomes available, should query separately:
1. `BYBIT` — expected primary linear/perpetual candidate;
2. `BYBITINVERSE` — inverse derivatives;
3. `BYBITUSDC` — USDC derivatives.

For each identifier, retrieve active and historical symbol pages, follow pagination to exhaustion, preserve the raw response and retrieval timestamp, and compare exchange-native symbol identifiers against the already-known Bybit cases (LUNAUSDT, USTUSDT, ANCUSDT, plus independently documented listings/delistings). Do not merge categories until duplicate and naming semantics are understood. For each matching symbol, record CoinAPI's data coverage dates separately from the actual Bybit lifecycle dates.

### Access and permission boundary

The endpoint requires an API key. No key is currently available in the authorized project context, and creating an account/key or starting a trial would cross the existing permission boundary. Therefore no live metadata request was made. This is not a technical failure and must not be described as a failed API test.

No paid plan, trial, API key, vendor account, data download, or market archive was created or accessed. A public documentation review is the furthest permissible step under the current authorization.

### Updated assessment

- **D4:** CoinAPI is now a more precisely scoped candidate, with at least three Bybit-related identifiers to test. It remains unverified because no actual symbol-history response or pagination count has been inspected. Its conditional retention policy prevents treating the vendor list as a complete Bybit universe without reconciliation.
- **D5:** remains missing. CoinAPI symbol precision metadata is not established as an effective-dated exchange-rule history.
- **D6:** remains missing. No historical risk-tier schedule or account-state reconstruction is established.

**Decision:** do not spend money or create an account/key just to test this lead. First use any already-authorized sample response if one is later supplied; otherwise request a vendor sample/coverage statement without committing to a subscription.


## 28. D5: bounded historical Bybit instrument-state stream is real, but field-level spec coverage is unproven

The Bybit Derivatives coverage page maintained by Tardis provides an exact capture boundary for the legacy public channel:
- Bybit Derivatives history begins 2019-11-07 for inverse and 2020-05-28 for linear.
- Legacy `instrument_info` was captured until 2023-04-05 and is described as “instrument ticker and contract state updates”.
- Tardis states that before 2023-04-05 collection used `wss://stream.bybit.com/realtime`; after that date it used the V5 public WebSocket infrastructure.
- The current documented Tardis channel list after 2023-04-05 includes `publicTrade`, `tickers`, and order-book channels, but no explicitly named replacement instrument-specification/state-update channel.

Reference: https://docs.tardis.dev/historical-data-details/bybit

This is a stronger and more precise D5 research lead than a generic market-data archive: it identifies an actual historical Bybit-originated stream and a bounded time interval. It does **not** yet establish that the captured payload contains every required specification field, or that all symbol updates were captured continuously.

### Field-level acceptance rule

Do not equate a contract-state stream with a complete instrument-specification history. Before accepting any Tardis `instrument_info` payload for D5, inspect a separately authorized sample and verify, field by field:
- `tickSize` / price increment and its event timestamp;
- `qtyStep` / quantity increment;
- minimum quantity and minimum notional;
- maximum limit, market and post-only quantities;
- price bounds;
- leverage bounds and leverage step;
- funding interval and funding-rate bounds where relevant;
- symbol identity, category, status, and lifecycle timestamps.

For each field, establish whether the message is a full snapshot or partial delta, how omitted fields are carried forward, whether updates are emitted on every exchange change, and whether the timestamp represents exchange event time or collector receive time. Preserve unknown intervals rather than interpolating values across gaps.

The current Bybit `Get Instruments Info` response exposes many of these fields, but that is a current-state endpoint; it does not make the old stream schema equivalent. The newer `Get Instrument Summary` endpoint returns only a narrower summary (including `qtyStep`, `tickSize`, and `deliveryTime`) and is also current-state, not historical.

Official references:
- https://bybit-exchange.github.io/docs/v5/market/instrument
- https://bybit-exchange.github.io/docs/v5/market/instrument-summary
- https://bybit-exchange.github.io/docs/changelog/v5

### D5 conclusion

- **2020/2023 bounded interval:** a real candidate exists in Tardis' historical `instrument_info` capture, but field completeness, per-symbol coverage, update semantics, and gap rates are not yet proven.
- **After 2023-04-05:** no equivalent complete public instrument-spec update stream is established by the reviewed Bybit/Tardis documentation.
- **Before the applicable collection start:** no evidence from this channel.
- **Current REST snapshots:** useful only from the moment they are independently captured; they cannot backfill historical changes.

D5 therefore remains **missing for acceptance**, although a bounded historical segment may be recoverable after an authorized sample-level audit. No Tardis API request, replay, download, account connection, or subscription was performed.

## 29. D6: risk-tier history is not the same thing as instrument leverage metadata

The current public `GET /v5/market/risk-limit` endpoint returns rows containing `riskLimitValue`, `maintenanceMargin`, `initialMargin`, `maxLeverage`, and `mmDeduction`, with cursor pagination. Its documented request parameters are category, symbol, and cursor; no effective-time or historical time-range parameter is documented.

Reference: https://bybit-exchange.github.io/docs/v5/market/risk-limit

The Bybit changelog records pagination changes and the addition of pre-market risk-limit support, but these are API/schema changes, not an archive of historical tier values:
- 2024-05-09: cursor pagination introduced for the linear risk-limit response.
- 2024-12-12: linear page size changed from 30 to 15.
- 2025-08-28: pre-market risk-limit tables supported.

Reference: https://bybit-exchange.github.io/docs/changelog/v5

### Account-state dependence makes a static tier table insufficient

Bybit's current risk-limit help article explains that effective tier selection can change dynamically with positions, active orders, and mark price. It also describes exchange-wide risk-parameter changes affecting IMR, MMR, maximum leverage, and position limits; email notices are not sent for every risk-limit adjustment. Depending on account risk, new parameters may apply immediately or after a buffer period.

Reference: https://www.bybit.com/en/help-center/article/Risk-Limit-Perpetual-and-Expiry-Contracts

The private Position stream exposes fields such as `riskId`, `riskLimitValue`, `positionValue`, `markPrice`, and `leverage`. These are account/position observations, not a public historical archive of all symbol tier schedules. The documentation also notes that `riskLimitValue` becomes meaningless when automatic risk-limit tiering is applied.

Reference: https://bybit-exchange.github.io/docs/v5/websocket/private/position

The API-announcement channel records the migration from manual tier selection to automatic tier adjustment beginning 2024-02-05. This is an important rules-regime boundary, but does not provide the full historical tier tables or each subsequent effective change:
https://t.me/s/Bybit_API_Announcements?before=217

### Minimum evidence required for D6

A valid reconstruction would need, for every symbol and effective interval:
1. The complete tier schedule: risk limit values, IMR/MMR, max leverage, maintenance-margin deduction, and tier identifiers.
2. Exchange-wide schedule-change events with announced/effective timestamps and any staged/buffer application rules.
3. The rule version for automatic tier selection, including the relevant position/order valuation logic.
4. For account-specific replay: positions, active orders, mark-price path, position mode, configured leverage, and any account-specific buffer/restriction state.
5. Explicit coverage and gap accounting. A current tier table or a few dated announcement examples cannot be interpolated into a complete history.

### D6 conclusion

- Public risk-limit REST endpoint: current lookup, not historical time series.
- Current help article: describes dynamic/current mechanics; historical applicability of every clause is not established.
- Announcements: selected rule-change evidence, not complete tier-value history.
- Private position stream: account-specific observations, not a substitute for public schedule history.
- No reviewed Tardis/CoinAPI metadata source establishes a complete effective-dated Bybit risk-tier archive.

**D6 remains structurally unaccepted for historical replay.** Even if a partial symbol-level tier history is later recovered, account-specific historical margin state must remain a separate requirement rather than being inferred from a static tier table.

No private API, account data, market data, paid vendor access, or execution was used.


## 30. Cross-check of the Tardis channel boundary and two dated risk-rule regime changes

A current, line-level review of the Tardis Bybit coverage page confirms the exact channel inventory and corrects how the historical stream should be interpreted:

- `instrument_info` is explicitly listed as available **until 2023-04-05**, described only as “Instrument ticker and contract state updates”.
- The old `trade` and `orderBookL2_25` channels also end on 2023-04-05.
- From 2023-04-05, Tardis lists V5 channels including `publicTrade`, `tickers`, and `orderbook.*`; it does **not** list a successor `instrument_info` channel.
- Tardis says historical messages are stored in the same format as the exchange WebSocket messages, with an additional local timestamp. The current Bybit V5 `tickers.{symbol}` schema contains market/ticker fields (last/mark/index price, funding, best bid/ask, delivery fields), but does not document `tickSize`, `qtyStep`, min notional, max order quantities, or risk-tier schedule fields.

References:
- Tardis Bybit channel inventory and collection boundary: https://docs.tardis.dev/historical-data-details/bybit
- Tardis message format: same as exchange WebSocket plus local timestamp, https://docs.tardis.dev/historical-data-details/bybit
- Bybit V5 ticker schema: https://bybit-exchange.github.io/docs/v5/websocket/public/ticker

This means the old stream remains a potentially useful **bounded contract-state/ticker evidence source**, but we must not promote it to a full D5 specification archive based only on its channel name. The schema-level evidence presently supports no claim that it contains the full REST instrument filters. A raw sample and legacy schema inspection would be required to determine whether any subset of specification fields is present.

The Tardis general collection documentation also describes checks for newly available instruments every minute. This is a discovery cadence, not a guarantee that every lifecycle transition or every mutable instrument parameter was captured. It cannot be used to infer continuous historical spec snapshots.

Reference: https://docs.tardis.dev/historical-data-details

### D5 revised conclusion

- Through 2023-04-05: Tardis `instrument_info` is a bounded historical candidate for contract state and possibly some instrument metadata, but field coverage and continuity remain unverified.
- From 2023-04-05 onward: documented V5 ticker and public-trade channels do not expose the full REST instrument filters needed for D5.
- No reviewed source establishes complete effective-dated history for tick size, quantity step, min notional, maximum order sizes, leverage bounds, and funding parameters across the full research interval.
- **D5 remains not accepted.** Do not treat market ticker feeds or Tardis instrument discovery as a substitute for effective-dated specification snapshots.

## 31. D6: two authoritative regime boundaries now identified

The documentary record provides two concrete, dated changes to risk/margin mechanics. These improve the regime timeline, but do not provide historical per-symbol tier tables.

### 31.1 Automatic risk-tier adjustment rollout — 2024-02-20

The Bybit API announcement states that automatic adjustment of Perpetual and Futures risk-limit tiers, based on position and active-order value, was postponed from 2024-02-05 to **2024-02-20**. The rollout covered USDT, USDC, and Inverse Perpetual/Futures. Manual tier selection was removed/disabled for users and the old Set Risk Limit API became ineffective for modifying the tier.

Reference: https://t.me/s/Bybit_API_Announcements?before=217

The changelog later records `Set Risk Limit` as deprecated on 2024-03-12 because automatic risk limit had launched:
https://bybit-exchange.github.io/docs/changelog/v5

For historical replay, 2024-02-20 is a documented rollout boundary, but “gradually changed” means it should not be assumed that every product/account transitioned atomically at one instant without further evidence. The March 12 deprecation is a later API/documentation boundary, not necessarily the first effective date for every account.

### 31.2 Mark-price-based margin/risk calculation — 2025-09-02

Bybit's Help Center article, last updated 2026-06-18, explicitly states that from **2025-09-02** it implemented a major margin-calculation update:
- Cross Margin IM/MM moved to Mark Price in the described contract modes.
- Isolated Margin MM moved to Mark Price while IM continued to use Entry Price.
- Risk-limit tiers began adjusting dynamically based on real-time Mark Price and combined position/order value.

Reference: https://www.bybit.com/en/help-center/article/Understanding-the-Adjustment-and-Impact-of-the-New-Margin-Calculation

This is a material risk-model regime boundary. A replay that uses only entry-price-based position valuation or assumes tiers change solely when orders/positions are opened/closed would be inconsistent with the documented post-2025-09-02 rules. The help article is current documentation with a stated implementation date; historical rollout exceptions and product/account eligibility still require confirmation if exact account-level liquidation replication is attempted.

### D6 implications and minimum reconstruction

The evidence now supports at least these distinct conceptual regimes:
1. Pre-auto-tier regime: manual risk tier selection / older adjustment semantics.
2. Automatic-tier regime beginning 2024-02-20: tier selected from positions and active orders.
3. Mark-price margin regime beginning 2025-09-02: relevant IM/MM and tier valuation logic uses Mark Price according to margin mode and contract type.

These are **rule-regime boundaries**, not tier-table values. For any historical replay that needs margin/liquidation fidelity, each regime still requires its applicable formulas, tier schedule, symbol-specific parameters, and account-state inputs. A dated rule announcement cannot supply missing historical tier rows.

### D6 revised conclusion

- We can now version the broad risk/margin rule regimes using official dated evidence for 2024-02-20 and 2025-09-02.
- We still cannot reconstruct the complete effective-dated risk-tier schedules for each symbol.
- We cannot reconstruct account-specific effective tier without positions, active orders, mark prices, leverage, margin mode, and applicable transition/eligibility state.
- **D6 remains unaccepted for historical economic replay.** The new findings reduce ambiguity about rule changes but do not close the data gap.

No Bybit endpoint was called. No Tardis replay/sample, private account data, market data, vendor subscription, archive download, collector, PnL run, or execution was used.


## 32. Official announcement archive is a partial event ledger for D5, not a complete specification history

A review of Bybit's current announcement catalogue and dated notices establishes that several mutable instrument constraints are published as explicit change events with old/new values and effective timestamps.

### 32.1 Tick-size events

Official USDT perpetual notices publish symbol-level current and new tick sizes and a UTC effective time. Examples found:
- 2026-06-05: selected contracts, effective 07:30 UTC.
- 2026-07-18: selected contracts, effective 05:00 UTC.
- 2026-08-11: selected contracts, effective 08:30 UTC.
- 2026-10-12: selected contracts, effective 07:30 UTC.
- 2026-11-20: selected contracts, effective 07:30 UTC.

Examples:
- https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-jun-5-2026-blt539f4749d220f97b/
- https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-jul-18-2026--art2c7f982380fe/
- https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-aug-11-2026--art4f47b6648755/
- https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-oct-12-2026--art5c4a8b8eef37/
- https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-nov-20-2026--art2a243e629ca8/

The Nov 20 notice also states that orders placed before the effective time remain in the book with the original tick size. Thus, for an order-book/execution replay, a single symbol-level tick value switched at the event time may still be insufficient to model grandfathered resting orders: order-level tick validity may depend on order placement time.

### 32.2 Maximum order-size events

Bybit's current Get Instruments Info documentation explicitly warns that `maxLimitOrderQty`, `maxMarketOrderQty`, and `postOnlyMaxLimitOrderSize` are adjusted twice monthly, on the 3rd and 17th at 08:00 UTC+8. It explicitly tells integrators not to assume these values remain constant.

Official endpoint documentation: https://bybit-exchange.github.io/docs/v5/market/instrument

The announcement catalogue contains many dated “Changes of Max. Order Size for USDT Perpetual Contracts” entries, including multiple updates in October–December 2025 and a Nov 20, 2026 notice. The Nov 20, 2026 notice gives before/after market and limit order sizes for SOXXUSDT and SNDKUSDT and an effective time of 12:30 UTC:
https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-nov-20-2026--arte1da2b0316fa/

This is direct evidence that max order quantities are mutable and that dated event notices can recover selected changes. It does not establish that every scheduled adjustment is individually announced, indexed without omissions, or preserved for the full historical interval.

### 32.3 D5 event-sourced recovery is possible only as a partial overlay

The official notices can populate a sparse, auditable event table for the exact fields they state:
- `tickSize`;
- maximum limit order size;
- maximum market order size;
- effective UTC timestamp;
- source URL and publication timestamp;
- any grandfathering/transition note.

Do not infer unchanged values between notices unless a complete baseline snapshot at the beginning of the interval and complete change-event coverage are both established. Missing notices must produce `unknown`, not carry-forward certainty.

The notices reviewed do not provide a complete historical record for `qtyStep`, `minOrderQty`, `minNotionalValue`, `priceFilter.minPrice/maxPrice`, leverage filters, funding bounds, and every other instrument field. D5 therefore remains **not accepted**, but its recovery path is now more concrete: dated official notices can supply partial field-specific changes, while snapshots are still required for complete state.

## 33. Official risk-limit notices expose a partial schedule-change ledger and account-specific transition windows

The official announcement catalogue contains repeated “Risk limit adjustment for selected Perpetual Contracts” notices, not just the isolated examples previously examined. Searchable catalogue entries include repeated updates through 2025 and 2026. The notices have materially different levels of detail.

### 33.1 Notices with explicit old/new leverage

The Sep 11, 2026 notice lists affected symbols and current/after maximum leverage values, with effective time 08:00 UTC:
https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-sep-11-2026--art85d833a97af0/

This is usable as a symbol-level event for the published maximum-leverage field. It is not a complete tier schedule: it does not provide every riskLimitValue, IMR, MMR, mmDeduction row for each affected contract.

### 33.2 Notices with delayed account application

Other notices describe an initial effective time and a later end of a buffer period. Examples:
- STORJUSDT: adjustment around 2026-09-04 03:30 UTC, buffer ends 2026-09-21 03:30 UTC.
  https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-storjusdt-sep-4-2026--arteb41cc67ea8b/
- AVAXUSDT, XLMUSDT and other contracts: initial adjustment around 2026-09-04 07:30 UTC, buffer ends 2026-09-21 07:30 UTC.
  https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-avaxusdt-xlmusdt-sep-4-2026--art453915b9e8fd/
- LYNUSDT, AGIUSDT, TMXUSDT, 1000RATSUSDT: initial adjustment around 2026-10-15 07:30 UTC, buffer ends 2026-11-01 07:30 UTC.
  https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-lynusdt-agiusdt-oct-15-2026--art83f2aa1db186/

The notices state that accounts unable to satisfy the new margin requirements may be restricted to reduce-only actions during the buffer period, and that existing positions may be subject to the new parameters after the buffer ends. They also reserve the right to end the buffer early for risk-control or emergency reasons.

Therefore a single global effective timestamp is not sufficient to reproduce every account's applied risk parameters. At minimum, preserve:
- announcement publication time;
- nominal scheduled adjustment time;
- buffer-period end;
- symbol scope;
- old/new values when explicitly disclosed;
- account-specific application state as unknown unless independently observed.

### 33.3 Current help-center mechanics confirm why a notice is not a complete account replay

The current Risk Limit help article (last updated 2026-09-04) states that effective position value uses Mark Price for USDT/USDC and inverse contracts, includes open positions and active orders, treats one-way and hedge position modes separately, excludes Reduce Only and Close on Trigger orders, and adjusts tiers in real time as Mark Price changes. It also documents a trial calculation and a 10-day buffer when an immediate application would create excessive account risk.

Reference: https://www.bybit.com/en/help-center/article/Risk-Limit-Perpetual-and-Expiry-Contracts

This establishes that historical D6 requires both:
1. the symbol's dated risk schedule/rules; and
2. the account's positions, orders, mark-price path, mode, leverage and transition state.

A public announcement may identify affected symbols and some parameter changes, but it does not expose the complete per-account rollout state.

### 33.4 D6 conclusion

- Official notices can recover selected symbol-level changes and some explicit maximum-leverage deltas.
- Some notices provide a buffer window, not a universal instantaneous effective time.
- The current REST risk-limit endpoint still has no documented historical time selector.
- No complete historical table of all tier rows and effective intervals has been established.
- **D6 remains unaccepted for historical account-level margin/liquidation replay.** Announcement-ledger work can reduce uncertainty for selected symbols and dates, but cannot substitute for the full tier history and account-state observations.

No API request, market-data download, private account access, paid subscription, collector, PnL replay, or execution was used.


## 34. Announcement API pagination does not establish historical retention or completeness

The current official V5 Get Announcement page documents:
- required `locale`;
- optional `type` and `tag`;
- `page` and `limit`;
- response `total`, `list`, publication timestamps and announcement URLs.

It does **not** document a publication-time range filter, a cursor tied to immutable history, a retention period, a completeness guarantee, or a maximum historical page depth.

Official reference: https://bybit-exchange.github.io/docs/v5/announcement

The official example's `total: 735` and ARB example timestamp are static documentation sample values, not a live count and not evidence that the endpoint currently retains all historical notices.

A historical Bybit V2 connector schema in the official `bybit-exchange/api-connectors` repository describes `/v2/public/announcement` as returning OpenAPI announcements from the **last 30 days** in reverse order. That older endpoint is explicitly unsuitable as a long-term event archive:
https://github.com/bybit-exchange/api-connectors/blob/master/swagger.json

A direct anonymous GET attempt to the V5 announcements endpoint from this research environment again failed at the web transport layer with “URL is not accessible”. No Bybit HTTP status, JSON response, `total`, earliest record, or pagination behavior was observed. This is a tooling/network limitation, not a Bybit rejection and not evidence that the endpoint is unavailable to a normal client. No other Bybit endpoint was attempted.

### D4 consequence

The V5 announcement endpoint remains a potentially useful discovery and retrieval interface, but its historical retention and completeness are unverified. Even a successful page walk to the last page would only establish exhaustion of the endpoint's currently exposed result set, not that Bybit retained every notice ever published. The older V2 endpoint's 30-day description reinforces that retention must be tested rather than assumed.

**Acceptance test still required:** once a successful permitted GET is possible, record raw response bytes, request parameters, retrieval time, `total`, per-page counts, first/last publication timestamps, duplicate IDs/URLs, locale/type/tag coverage, and page-walk termination. Then reconcile known listing/delisting/tick-size/risk-limit notices against independently collected official notice URLs. A page walk alone cannot pass D4; known-case recall and explicit retention boundary are required.

D4 remains **partial/unverified**.

## 35. Public GitHub ecosystem audit: no qualifying historical D5/D6 archive found

A read-only GitHub code search was performed for:
- Bybit historical instrument specifications, tickSize and qtyStep snapshots;
- historical risk-limit tier rows and maxLeverage/maintenanceMargin values;
- legacy `instrument_info` contract-state payloads;
- instrument/risk-limit snapshot archives.

The search surfaced useful corroborating engineering references, but no public dataset with a symbol-complete, effective-dated Bybit specification or risk-tier history.

### 35.1 Independent reference catalogs

The public TriggerTrade raw-data catalog classifies:
- Instruments Info as reference data/current metadata that must be refreshed;
- Risk Limit as reference data, not a historical research time series by default.

It also explicitly distinguishes historical market-data endpoints from current reference endpoints. This is a third-party methodology document, not Bybit authority, but its classification agrees with the official API request schemas:
https://github.com/Lugovele/trigger-trade/blob/d3aec0a333ddf78e84b2ef625c00d3064780b0db/docs/archive/trading-methodology-pre-v1.2.14/data/BYBIT_RAW_DATA_CATALOG.md

A separate Bybit venue audit in another public repository states that its instrument-spec source is today's `instruments-info` and `risk-limit` REST response, and that delisted symbols are not served by those current lookups. This is a third-party observation, not a guarantee about every API retention case:
https://github.com/sbOogway/sbt2/wiki/Source-Bybit

### 35.2 A good snapshot pattern is not a historical archive

A public GitHub implementation found during the search contains one captured BTCUSDT linear instrument response, with:
- a specific retrieval timestamp (2026-09-14);
- the raw response object preserved;
- a SHA-256 payload hash;
- derived instrument values tied to that exact source snapshot.

This is a useful provenance pattern for future snapshots, but the inspected code contains a single symbol/single capture example, not a time series or historical universe:
https://github.com/omerasik/investing_tradin_platform/blob/14d62c46a10822f618186f822deca1f85d2d59c3/src/trade_platform/bybit_instrument_onboarding.py

Its tests explicitly bind `effective_at` to the snapshot's retrieval time. That is honest observation-time provenance, but it must not be mistaken for the exchange's historical effective time of the parameter change.

### 35.3 Repository search findings are not proof of non-existence

GitHub code search is incomplete by design: private repositories, unindexed files, binary datasets, deleted history, and differently named artifacts may not appear. Therefore the result is:
- no qualifying public archive identified in this search;
- not a proof that no such archive exists anywhere;
- no third-party source is promoted to exchange-authoritative evidence.

### 35.4 D5/D6 disposition

- D5: current snapshots and selected announcement events can be retained as future point-in-time evidence, but no accepted full historical spec series has been found.
- D6: selected risk notices and dated rule changes can be recorded, but no accepted full symbol-tier history or account-state history has been found.
- No new dataset has passed provenance, completeness, field coverage, effective-time semantics, and gap accounting.

**DATA GATE REMAINS BLOCKED.** No market archives were downloaded, no API collectors were run, no private/account endpoints were called, no vendor account or subscription was created, and no PnL/backtest/execution was run.


## 36. Official linkmap sampling: useful discovery index, not a chronological completeness proof

A read-only sample of official announcement linkmap pages 4–12 was inspected. It confirms that the catalogue exposes many relevant article slugs, including:
- repeated derivatives max-order-size notices (e.g. Oct 5, Oct 9, Oct 11, Oct 14, Oct 16–24 and Nov 3–18, 2025);
- repeated USDT perpetual tick-size notices (e.g. Oct 9, Oct 21, Oct 29 and Nov 6, 2025; Jan 9, Jan 15, Jan 22 and Jan 27, 2026; Feb 3 and Feb 9, 2026);
- repeated derivatives risk-limit notices (e.g. Oct 20 and Oct 22, 2025; Jan 8–28 and Feb 26–27, 2026);
- multiple perpetual-contract delistings.

Sampled official catalogue pages:
- https://announcements.bybit.com/en/linkmap/4/
- https://announcements.bybit.com/en/linkmap/5/
- https://announcements.bybit.com/en/linkmap/6/
- https://announcements.bybit.com/en/linkmap/7/
- https://announcements.bybit.com/en/linkmap/8/
- https://announcements.bybit.com/en/linkmap/9/
- https://announcements.bybit.com/en/linkmap/10/
- https://announcements.bybit.com/en/linkmap/11/
- https://announcements.bybit.com/en/linkmap/12/

The sampled pages are not safely interpretable as a simple oldest-to-newest sequence: publication dates in the visible entries do not monotonically follow the page number, and repeated article slugs occur across sampled pages. Therefore:
- page number cannot be used as a date proxy;
- the apparent count of linkmap pages cannot be translated into a reliable time-depth estimate;
- sitemap presence proves discoverability of a specific URL, not that all notices in a period are present;
- this sample does not establish whether the catalogue reaches 2024, 2023, or earlier.

Individual article pages can also be rendered in localized language variants and may expose only title/publication date in the accessible page extraction. For example, the Nov 6, 2025 tick-size article is discoverable from the catalogue, but the extracted localized page did not expose the full old/new parameter table. A URL in the catalogue is therefore not by itself a structured event record.

Official V5 API documentation confirms that `/v5/announcements/index` has `page` and `limit`, returns `total` and `list`, and exposes publication-related timestamps. It documents no time-range filter, retention period, or historical completeness guarantee:
https://bybit-exchange.github.io/docs/v5/announcement

The documentation response example contains a static `total: 735` and an ARB listing timestamp from March 2023; these are example payload values, not a live API count or proof of current retention. A permitted anonymous GET to the exact V5 announcements endpoint was attempted from the research web environment, but the tool reported the URL inaccessible. No HTTP response or live payload was obtained. No other Bybit API endpoint was called.

### Updated D4/D5/D6 implication

The official catalogue is a valuable **event-discovery source** and confirms that changes are frequent enough that carrying current metadata backward is unsafe. However, the sampled catalogue does not provide a defensible completeness boundary or continuous effective-dated event ledger.

Keep announcement-derived events as individually sourced observations. Do not forward-fill a parameter across an interval unless a trustworthy baseline and complete change coverage for that symbol/field/period are independently established. Otherwise the value remains unknown.

D4 remains **partial/unverified**. D5 and D6 remain **not accepted** for historical replay.


## 37. Re-audit of the 2023-04-04 changelog anomaly: not historical instrument lookup

The V5 changelog contains a misleading entry dated 2023-04-04:

- Its visible label says **Get Instruments Info** and claims `startTime` / `endTime` were added, effective for UTA.
- However, the hyperlink attached to that label resolves to the official **Get Order History** page, endpoint `GET /v5/order/history`, not Get Instruments Info.
- The immediately following separate 2023-04-04 entry is also Get Order History and describes the same `startTime` / `endTime` parameters.

Official evidence:
- Changelog entry: https://bybit-exchange.github.io/docs/changelog/v5
- The link attached to the suspicious label resolves to: https://bybit-exchange.github.io/docs/v5/order/order-list
- Current Get Instruments Info request schema: https://bybit-exchange.github.io/docs/v5/market/instrument

The current Get Instruments Info schema lists `category`, `symbol`, `symbolType`, `status`, `baseCoin`, `limit`, and `cursor`; it does not list `startTime` or `endTime`. Its description is to query instrument specifications of online trading pairs. The current Get Order History schema explicitly lists `startTime` and `endTime`, including a maximum seven-day query window.

The most defensible interpretation is a **changelog hyperlink/label copy-paste error**, not proof that Get Instruments Info ever supported historical specification queries. The earlier Section 20 correction therefore stands. No request was sent to either market endpoint.

### Consequence

Do not reopen the historical `instruments-info` API path based on the 2023-04-04 changelog line. D5 remains without a documented historical query mechanism in the current official endpoint. The historical event-ledger and baseline-snapshot requirements remain unchanged.


## 38. Official market API and risk-limit documentation: historical-data boundary

Read-only review of the current official V5 documentation establishes the following:

### Instrument specifications (D5)

- `GET /v5/market/instruments-info` is described as querying specifications for **online trading pairs**. Its documented request parameters are category, symbol, symbolType, status, baseCoin, limit and cursor; there are no documented historical time parameters.
- The response includes launchTime and deliveryTime, but these describe instrument lifecycle bounds, not historical versions of tickSize, qtyStep, minNotionalValue, leverageFilter, funding bounds or order-size limits.
- The documentation explicitly warns that max order quantity fields are adjusted twice monthly (3rd and 17th, 08:00 UTC+8), so a present-day value cannot safely be projected backward.
- `GET /v5/market/instrument-summary`, introduced 2026-10-14, is a current summary endpoint and does not document historical versions either.

Official references:
- https://bybit-exchange.github.io/docs/v5/market/instrument
- https://bybit-exchange.github.io/docs/v5/market/instrument-summary
- Changelog: https://bybit-exchange.github.io/docs/changelog/v5

### Risk-limit tables versus actual account tier (D6)

- `GET /v5/market/risk-limit` returns the current per-symbol risk-tier table (riskLimitValue, IMR, MMR, maxLeverage, mmDeduction) with cursor pagination. Its documented request has no effective-time or historical query parameter.
- Bybit's risk-limit help article states that automatic tier selection depends on the account's open positions and active orders. Effective position value is calculated using mark price; reduce-only and close-on-trigger orders are excluded. As mark price and open orders/positions change, the account's tier can change in real time.
- The same help article distinguishes Isolated/Cross modes from Portfolio Margin. Portfolio Margin calculates risk at the overall account portfolio level rather than using the symbol risk-limit table in the same way.

Official references:
- https://bybit-exchange.github.io/docs/v5/market/risk-limit
- https://www.bybit.com/en/help-center/article/Risk-Limit-Perpetual-and-Expiry-Contracts

Therefore two different historical objects must not be conflated:
1. **Exchange tier schedule:** the dated tier rows and parameter changes for a symbol.
2. **Account's applied tier/state:** the tier actually applicable at a moment, derived from that account's positions, active orders, mark prices, leverage and margin mode.

A historical tier schedule alone is insufficient to reproduce an account's liquidation/margin path. D6 needs both dated exchange tier schedules and account-state inputs if account-level liquidation is in scope.

### Official historical market-data downloads are not a spec archive

The V5 Get Recent Public Trades documentation links to Bybit's Historical Data download page. This confirms an official route for archived historical trade data, but the cited documentation does not describe a historical instrument-specification or risk-tier archive. It must not be treated as evidence that D5/D6 are solved:
- https://bybit-exchange.github.io/docs/v5/market/recent-trade
- https://www.bybit.com/en/derivative-activity/history-data

A third-party Bybit adapter's source notes also describe instrument-info and risk-limit as today's specification only and state that delisted symbols are not served by those current endpoints. This is corroborative implementation evidence, not an official completeness guarantee:
- https://github-wiki-see.page/m/sbOogway/sbt2/wiki/Source-Bybit

### Gate decision

- D5 remains **NOT ACCEPTED**: current specs plus lifecycle timestamps and event notices do not form a complete effective-dated history.
- D6 remains **NOT ACCEPTED**: current tier tables and selected announcements do not form a complete tier history; account-specific applied tiers require account-state reconstruction.
- Official trade archives may help a later, separately authorized market-data stage, but do not close D4/D5/D6.
- No archive was downloaded, no collector or API endpoint was run, no market calculation/backtest was run, and no permission boundary was changed.


## 39. Bybit official documentation Git history: schema chronology recovered, historical values not recovered

### Repository and coverage

Bybit publishes its V5 API documentation in the public GitHub repository:
https://github.com/bybit-exchange/docs

The repository metadata reports creation on 2022-11-14 and active updates through 2026-11-23. Its current default branch is `master`. The Git history for `docs/v5/market/instrument.mdx` contains 100 commits in the queried history, with the oldest returned commit dated 2022-12-05; a second page returned no additional commits. The corresponding `docs/v5/market/risk-limit.mdx` history contains 34 commits and also reaches 2022-12-05.

This is a real, useful version history of the **documentation contract**. It is not an archive of the API's per-symbol response values.

### Recovered instrument-schema milestones

The following changes are visible in the official docs Git history and/or the official V5 changelog:

| Date | Documented change | What it proves |
|---|---|---|
| 2022-12-05 | Initial V5 instrument and risk-limit pages in the public docs history | Earliest schema evidence found in this repository |
| 2023-04-06 | Instrument status filter added | API query coverage changed; not a complete lifecycle event log |
| 2024-01-18 | Spot instrument risk-parameter documentation updated | Schema/field coverage evolved |
| 2024-02-06 | `upperFundingRate` and `lowerFundingRate` added to instrument response | These fields must not be assumed present before this date |
| 2024-02-21 | `maxMktOrderQty` added; `postOnlyMaxOrderQty` deprecated/replaced by `maxOrderQty` for the documented order types | Order-size schema changed |
| 2024-06-27 | `Closed`, `Delivering`, and `PreLaunch` status filters documented for linear/inverse | Earlier default/status coverage cannot be assumed equivalent |
| 2025-01 | Derivatives limit-order price formula change referenced by instrument docs | `riskParameters` semantics changed, not merely a field name |
| 2025-10-09 | Spot `maxLimitOrderQty` and `maxMarketOrderQty` added | Spot size limits gained distinct market/limit fields |
| 2025-10-23 | Spot `maxOrderQty` and `maxOrderAmt` marked deprecated | Backward compatibility assumptions changed |
| 2025-11-03/11 | Spot `postOnlyMaxLimitOrderSize` documented | Further order-type-specific field introduced |
| 2026-02-12 | Docs warn that `maxLimitOrderQty`, `maxMarketOrderQty`, and `postOnlyMaxLimitOrderSize` are adjusted on the 3rd and 17th of each month at 08:00 UTC+8 | These values are explicitly time-varying |
| 2026-05-27 | Derivatives limit-order price formula reference updated to May 2026 | Another effective rule change requiring date-aware interpretation |
| 2026-09-29 | `tags` response field added | Current schema contains fields absent from earlier versions |

Useful primary history links:
- Initial instrument page: https://github.com/bybit-exchange/docs/commit/f18a4894ec8df9cfe762f6d8f03f0790e8b82c37
- Status filter: https://github.com/bybit-exchange/docs/commit/423d67c0775e378f3cb676b83dae32962b44000d
- Funding-rate bounds: https://github.com/bybit-exchange/docs/commit/208e13bc0447b0d520593b6872d025264d0a93ae
- Max market quantity: https://github.com/bybit-exchange/docs/commit/b689da76f0ec934376fd8ea2049a44f67d54f741
- Spot market/limit quantity fields: https://github.com/bybit-exchange/docs/commit/ca2d8136b84b29e99fffc68cfa702515f97a9e53
- Spot legacy-field deprecation: https://github.com/bybit-exchange/docs/commit/df666b4a3bc8dba3c76cf7d29beaec35afa54f1d
- Dynamic size-field warning: https://github.com/bybit-exchange/docs/commit/302c912ae9e1844d7d59979dfb9ccee31e284763
- May 2026 price-limit formula reference: https://github.com/bybit-exchange/docs/commit/b3f09bd5621e2b0edbb7639607d58b35de0c6505
- Full current V5 changelog: https://github.com/bybit-exchange/docs/blob/master/docs/changelog/v5.mdx

### Recovered risk-limit API chronology

The official risk-limit page history shows:
- Initial response contract in December 2022 included `riskLimitValue`, `maintenanceMargin`, `initialMargin`, `isLowestRisk`, and `maxLeverage`.
- On 2024-05-09, cursor pagination was documented and linear requests returned 30 symbols per page.
- On 2024-12-12, the documented page size changed from 30 to 15 symbols per request.
- On 2025-08-28, querying risk-limit tables for PreLaunch contracts was added.
- The current response schema includes `mmDeduction`; the historical example response is still a single BTCUSD tier followed by ellipses, not a complete tier table.

Primary history:
- Initial risk-limit documentation: https://github.com/bybit-exchange/docs/commit/f18a4894ec8df9cfe762f6d8f03f0790e8b82c37
- Cursor/30-symbol pagination: https://github.com/bybit-exchange/docs/commit/f294053e29816ccd8e1a037fd27021dd43452b10
- 15-symbol page size: https://github.com/bybit-exchange/docs/commit/54d23664ddea5f8e7ce95bcdbb9aeea96feb2b72
- PreLaunch support: https://github.com/bybit-exchange/docs/commit/38a6faa02add1c5429cc44e3f0cf708f0be2413b
- Current risk-limit page: https://github.com/bybit-exchange/docs/blob/master/docs/v5/market/risk-limit.mdx

### What the documentation examples can and cannot contribute

The original instrument documentation contains example response payloads with millisecond `time` fields from late December 2022. The current instrument page also contains a BTCUSDT linear example with a timestamp from early January 2025. These are potentially useful as **dated illustrative specimens** for field names and isolated example values.

However, they are not accepted historical snapshots:
- the documentation does not provide the original request/response capture manifest, full raw response archive, or proof that the example was retained unchanged from a production capture;
- examples cover only selected categories/symbols and do not establish complete symbol coverage;
- example payloads may be revised independently of the underlying historical API state;
- the current risk-limit example still carries a December 2022 `time` value and shows only one BTCUSD tier before an ellipsis, so it cannot represent a current or complete risk table.

Do not ingest documentation examples as production metadata or silently forward-fill them. Preserve them only as weak corroborative evidence unless independently reconciled against a source capture.

### Updated assessment

1. **Schema history is partially recoverable.** The official Git history provides a credible timeline of when documented fields, filters, and response semantics were introduced or revised, beginning in December 2022.
2. **Historical numeric specification values are not recovered.** The repository does not contain a complete effective-dated per-symbol series for tick size, quantity steps, min notional, leverage bounds, funding limits, or max order sizes.
3. **Historical risk-tier values are not recovered.** The docs show endpoint shape changes and a truncated example, not full per-symbol tier tables over time.
4. **Documentation commit date is not automatically the market-effective timestamp.** Use the official changelog/announcement's effective time where explicitly provided; otherwise store the documentation commit date only as a publication/version observation, not as a parameter effective time.

D5 remains **NOT ACCEPTED**. D6 remains **NOT ACCEPTED**. The docs repository materially improves schema chronology and auditability, but it does not close the historical data gate.


## 40. Third-party dated Bybit metadata snapshots: partial raw captures and cross-source replication

A targeted public-GitHub search found two separate projects preserving Bybit mainnet metadata responses. This changes the previous assessment: **dated candidate snapshots do exist**, although they do not yet meet the project's full-universe, interval-coverage, and provenance acceptance requirements.

### Source A — crypto-dashboard, capture beginning 2026-09-29

Repository: https://github.com/mannar-hielal/crypto-dashboard

- Committed fixture: https://github.com/mannar-hielal/crypto-dashboard/blob/main/apps/server/fixtures/bybit/recorded.json
- Recorder source: https://github.com/mannar-hielal/crypto-dashboard/blob/main/apps/server/src/tools/recordBybitFixtures.ts
- Commit adding fixture: https://github.com/mannar-hielal/crypto-dashboard/commit/3674bed796bdbc15b89ee774242734a721a331dd
- Fixture Git blob SHA: `edd5ad5958b0a5dbaf53cf7917f4ce314b33f162`
- Embedded `recordedAt`: `2026-09-29T03:36:42.964Z`
- Embedded source: `https://api.bybit.com`

The recorder source documents unauthenticated public mainnet GETs and shows the exact query shapes. The committed fixture contains:
- 9 Spot instrument rows and 9 Linear instrument rows: BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK;
- risk-limit arrays for those same 9 Linear symbols, with 30–35 rows per symbol;
- additional ticker/orderbook/funding/kline/WS fixtures, outside the present metadata assessment.

Important provenance limitation: the script stores the API `result` objects, not the complete REST response envelope. It sets one `recordedAt` before making a sequence of requests, and does not preserve each response's server `time`, request ID, or per-symbol retrieval timestamp. It is therefore a dated capture window, not an atomic point-in-time snapshot. The raw fixture is more useful than a hand-entered table, but its exact per-row capture time is not independently established.

The derivative fallback in `apps/server/src/trading/bybitSpec.ts` is not a second independent dataset. It is a reduced implementation copy: instrument rules are reduced to four fields and risk tiers are truncated at the first tier below the project's 10× leverage cap. Use the original `recorded.json` for evidence, not that fallback.

### Source B — sleeve-fund, raw API captures on 2026-10-15 and 2026-10-21

Repository: https://github.com/aoventuresdomain-cloud/sleeve-fund

**2026-10-15 BTCUSDT risk-limit corroboration (manually pasted, not a recorder capture)**
- File: https://github.com/aoventuresdomain-cloud/sleeve-fund/blob/7c04fe480883578a52ef581709209af85b039fed/tests/data/fee_live/risk-limit-BTCUSDT-2026-10-15.json
- Commit: https://github.com/aoventuresdomain-cloud/sleeve-fund/commit/7c04fe480883578a52ef581709209af85b039fed
- Embedded JSON `time`: `2026-10-15T10:26:49.276Z`; 35 BTCUSDT risk tiers; `nextPageCursor` empty.
- The repository's `tests/data/fee_live/README.md` explicitly says the PM pasted this public risk-limit page on Oct 15 and the DA hand-checked it. Treat it as manually sourced corroboration, **not** as a second direct recorder/API capture. The same README says its neighboring fee-rate file was not captured from an account and its neighboring instrument-info file was written to the documented shape, not captured; neither of those files is accepted evidence.

**2026-10-21 venue-table capture**
- Capture marker: https://github.com/aoventuresdomain-cloud/sleeve-fund/blob/c72e9391c1c98e3c31d26a83ea7f5c731fa83ba3/tests/data/venue_tables/read-at.txt
- Commit: https://github.com/aoventuresdomain-cloud/sleeve-fund/commit/c72e9391c1c98e3c31d26a83ea7f5c731fa83ba3
- Capture marker: `2026-10-21T21:30:27+00:00`
- Raw BTCUSDT instrument response: https://github.com/aoventuresdomain-cloud/sleeve-fund/blob/c72e9391c1c98e3c31d26a83ea7f5c731fa83ba3/tests/data/venue_tables/instruments-info-BTCUSDT.json
- Raw risk-limit responses: BTCUSDT, ETHUSDT, SOLUSDT and XRPUSDT under `tests/data/venue_tables/`.
- The BTC instrument response server `time` is `2026-10-21T21:30:28.189Z`; the BTC risk-limit response server `time` is `2026-10-21T21:30:28.021Z`. The other three risk responses were returned within the same second.
- Each of the four risk files contains 35 tiers and an empty `nextPageCursor`.

The source workflow is inspectable:
https://github.com/aoventuresdomain-cloud/sleeve-fund/blob/c72e9391c1c98e3c31d26a83ea7f5c731fa83ba3/.github/workflows/venue-tables.yml

It documents a manually dispatched, read-only public GET workflow, preserves complete JSON response envelopes, follows risk-limit cursors (up to its configured safety cap), and records a UTC capture marker. The checked-in files are raw response JSON, not only normalized tier tuples. The committed instrument-info sample is BTCUSDT only; do not infer that instrument rows for ETH/SOL/XRP were preserved just because their risk tables were.

### Cross-source checks performed

The two projects' risk-limit rows compare **exactly**, including IDs and every tier field, for all 35 tiers of each overlapping symbol:
- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT

The manually pasted 2026-10-15 BTCUSDT tier file also compares exactly with the 2026-10-21 BTCUSDT raw response across all 35 tiers, but its weaker manual provenance means this is corroboration rather than a second independent raw capture. The 2026-10-21 BTCUSDT instrument-info response compares exactly, field-for-field, with the BTCUSDT Linear row in the 2026-09-29 crypto-dashboard fixture.

This is meaningful cross-project replication for those symbols and dates. It does **not** prove that no parameter changed between captures, nor does it recover values before the first capture. The agreement is a consistency check across snapshots, not a complete history.

### Independent lifecycle cross-check: BNBUSDT tick

The 2026-09-29 crypto-dashboard fixture records BNBUSDT Linear `tickSize=0.1`. Bybit's official Oct 8 announcement states that BNBUSDT USDT Perpetual tick size would change from `0.1` to `0.01` by 2026-10-12 07:30 UTC, and that resting orders placed before the change would retain their original tick:
https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-oct-12-2026--art5c4a8b8eef37/

The crypto-dashboard project's Oct 12 commit then records that its live spec-drift check found the BNBUSDT tick changed from 0.1 to 0.01 and updates its Spot and Linear fallback values:
https://github.com/mannar-hielal/crypto-dashboard/commit/f217f1860b65aaf0c78a96db84e6d6de2f1dd4a7

This is a useful three-part consistency chain for **BNBUSDT Linear**: dated pre-change snapshot → official effective-time announcement → later third-party drift observation. The announcement itself covers USDT Perpetual, not Spot; do not treat it as official evidence for the Spot change.

### Updated D5/D6 assessment

| Requirement | New evidence | Remaining gap | Decision |
|---|---|---|---|
| D5 — instrument specs | 9-symbol Spot+Linear result fixture at 2026-09-29; raw BTCUSDT Linear response at 2026-10-21; exact BTC overlap; BNB tick event cross-checked | No continuous effective-dated history, only one raw BTC instrument response in the second project, incomplete full-market coverage, no long historical interval | **PARTIAL CANDIDATE EVIDENCE — NOT ACCEPTED** |
| D6 — exchange risk tiers | 9-symbol tier fixture at 2026-09-29; raw 4-symbol tables at 2026-10-21; a manually pasted BTC table dated 2026-10-15; exact 35-tier cross-source matches for BTC/ETH/SOL/XRP | Only four symbols have raw cross-project replication; the Oct 15 BTC corroboration is manually pasted; short time span; no full historical tier-change ledger; no account-specific applied-tier/position/order state | **PARTIAL CANDIDATE EVIDENCE — NOT ACCEPTED** |

These snapshots are not yet imported into the project repository and are not authorized for historical market-PnL replay. They should be treated as source leads for a future provenance acceptance package, not as permission to start collectors or market tests. No Bybit endpoint was called by this research session, no new market archive was downloaded, and no backtest/PnL calculation was run.


## 41. Coverage of dated metadata snapshots against the exact E11/E13 47-symbol proxy universe

### Recovering the denominator from the original workflow logs

The exact universe was recovered from historical GitHub Actions logs, not inferred from the shortlist in `scripts/h1_symbol_universes.json`:

- E11 run: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41361376448
- E11 repeat run: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41361285396
- E13 run: https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41362217727

Both E11 runs and the E13 run report `Valid H1 symbols=50; fold-eligible symbols=47; common aligned bars=4321`, then print the complete sorted 47-symbol universe. All three lists are identical. This is the exact E11/E13 replay universe, not the 5-symbol primary or 5-symbol reserve shortlist.

The 47 symbols are:

`AAVEUSDT, ADAUSDT, ALGOUSDT, APTUSDT, ARBUSDT, ASTERUSDT, ATOMUSDT, AVAXUSDT, BCHUSDT, BNBUSDT, BTCUSDT, CAKEUSDT, DASHUSDT, DOGEUSDT, DOTUSDT, ENAUSDT, ETCUSDT, ETHUSDT, GMXUSDT, HBARUSDT, ICPUSDT, JSTUSDT, LINKUSDT, LTCUSDT, MINAUSDT, MORPHOUSDT, NEARUSDT, ONDOUSDT, PAXGUSDT, PEPEUSDT, POLUSDT, PUMPUSDT, QNTUSDT, RAYUSDT, RENDERUSDT, SHIBUSDT, SKYUSDT, SOLUSDT, SUIUSDT, TAOUSDT, TRXUSDT, UNIUSDT, WLDUSDT, WLFIUSDT, XLMUSDT, XRPUSDT, ZECUSDT`.

The log prints `UNIVERSE <symbol>` and bar/fold counts for each row. At the time of the initial comparison, no workflow artifact ZIP had been downloaded; the later read-only artifact verification is recorded in Section 42. No market archive was downloaded.

### Exact overlap with the dated metadata snapshots

The 2026-09-29 `crypto-dashboard` fixture contains nine Linear symbols. All nine are present in the E11/E13 universe:

`ADAUSDT, AVAXUSDT, BNBUSDT, BTCUSDT, DOGEUSDT, ETHUSDT, LINKUSDT, SOLUSDT, XRPUSDT`.

- D5 candidate instrument-spec coverage: **9 / 47 = 19.1%** of the E11/E13 proxy universe at the 2026-09-29 capture window.
- D6 candidate risk-tier coverage: **9 / 47 = 19.1%** at the same capture window.
- The additional 9 Spot rows in that fixture do not increase coverage of this Linear perpetual universe; they are a different product category.

The 2026-10-21 `sleeve-fund` raw captures cover:
- D5 instrument info: BTCUSDT only, **1 / 47 = 2.1%**.
- D6 risk tiers: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, **4 / 47 = 8.5%**.

The four raw Oct 21 risk-tier symbols are all inside the Sep 29 nine-symbol fixture, and all 35 tiers for each symbol compare exactly between the two projects. Thus the raw cross-project D6 replication covers four of the 47 proxy symbols, not nine. The Oct 15 manually pasted BTC table adds no new symbol or independent raw-capture coverage.

The 38 symbols outside the Sep 29 nine-symbol fixture are:

`AAVEUSDT, ALGOUSDT, APTUSDT, ARBUSDT, ASTERUSDT, ATOMUSDT, BCHUSDT, CAKEUSDT, DASHUSDT, DOTUSDT, ENAUSDT, ETCUSDT, GMXUSDT, HBARUSDT, ICPUSDT, JSTUSDT, LTCUSDT, MINAUSDT, MORPHOUSDT, NEARUSDT, ONDOUSDT, PAXGUSDT, PEPEUSDT, POLUSDT, PUMPUSDT, QNTUSDT, RAYUSDT, RENDERUSDT, SHIBUSDT, SKYUSDT, SUIUSDT, TAOUSDT, TRXUSDT, UNIUSDT, WLDUSDT, WLFIUSDT, XLMUSDT, ZECUSDT`.

### Interpretation — useful coverage, not a point-in-time universe

This comparison makes the gap measurable: the dated candidate fixture covers 19.1% of the exact 47-symbol research sample, and the second project's raw captures cover only one instrument-spec row and four risk-tier rows.

However, **the 47-symbol denominator is itself not a Bybit point-in-time universe**. E11/E13 formed it from the Binance-style proxy archive by retaining symbols with enough common history across all three folds. The sample spans 2026-04-29 to 2026-10-26, but it is fixed, availability-filtered and survivor-biased. A matching ticker in a third-party Bybit fixture does not prove that the same Bybit contract was listed and tradable throughout the entire proxy interval.

Therefore:
- the percentages quantify overlap with the research sample only;
- they do not estimate coverage of all Bybit Linear contracts;
- they do not close D4 lifecycle/PIT-universe requirements;
- they do not close D5 historical effective-time parameter coverage;
- they do not close D6 historical tier schedule or account-applied-tier history.

### Updated decision

D5 and D6 remain **PARTIAL CANDIDATE EVIDENCE — NOT ACCEPTED**. The next highest-value source search is for additional dated raw Bybit Linear instrument/risk-limit captures covering the 38 currently uncovered symbols and earlier dates, with per-response server timestamps and original request/response envelopes. Do not import third-party files or start any PnL/backtest until provenance acceptance and existing authorization gates are separately satisfied.


## 42. E11/E13 workflow artifact manifest cross-check (read-only verification)

After Section 41 was drafted from workflow logs, the two pre-existing result artifacts were downloaded for a stronger manifest-level check:
- E11 run 41361376448, artifact 13105661683 (e11-h1-shared-capital-portfolio.zip).
- E13 run 41362217727, artifact 13105403824 (e13-h1-compression-gate.zip).

Only the already-existing research result ZIPs were downloaded. No CryptoFetch/Bybit market archive was downloaded and no workflow was dispatched.

Both ZIPs contain their own universe manifest CSV. The two manifests compare IDENTICALLY across all 50 rows and all 10 columns, not merely by the 47-symbol subset. Each has 47 included rows and the same three exclusions: AEROUSDT, GRAMUSDT and HYPEUSDT, each excluded for fewer than 100 bars in one or more folds. The six source-archive SHA-256 entries also match exactly between E11 and E13.

This independently confirms the exact denominator and universe used in Sections 41 and the E11/E13 reports. It does not change the coverage percentages or data-gate decision; it upgrades the evidence for universe identity from log text to the original run artifacts. The manifests describe the Binance-style proxy sample and do not establish a Bybit point-in-time universe.

No market calculations were performed on the artifacts. D4 remains partial/unverified; D5/D6 remain PARTIAL CANDIDATE EVIDENCE / NOT ACCEPTED.


## 43. sbOogway/sbt2 — daily instrument snapshots are a source lead, not a public archive

A public Bybit data-source adapter in [sbOogway/sbt2](https://github.com/sbOogway/sbt2) documents one UTC-dated instrument snapshot per symbol under `raw/bybit/linear/{SYM}/instrument/{SYM}{YYYY-MM-DD}.json`. Its parser initializes the instrument snapshot at 00:00 UTC on the capture date. The adapter's source code constructs this dated file through a current public REST request to `instruments-info` plus `risk-limit`.

Important limitations established from the source code and repository:
- The API method explicitly documents **today's spec**, not a historical query. The wiki says delisted symbols are not served. A daily filename means the adapter can create a dated observation when run; it does not prove that a historical daily series exists.
- The snapshot method calls `_lowest_risk_tier()` and stores only the tier marked `isLowestRisk` as `margin_init` / `margin_maint`. It does **not** preserve the full risk-limit table in each instrument snapshot. Therefore this is not a D6 full-tier-history source.
- The public repository's current tree has no `raw/bybit/` data files. Its `.gitignore` excludes `/data/` and `/sbt2-backend/data/`; the wiki describes raw/catalog data as local storage. The public repo therefore exposes the capture mechanism, not the generated daily archive.
- A committed test fixture `bybit_responses.json` contains a BTCUSDT instrument-info response and a full 35-tier risk-limit response. It is a test fixture, not a multi-date series or a complete symbol universe.

Source inspection:
- Wiki: https://github-wiki-see.page/m/sbOogway/sbt2/wiki/Source-Bybit (last modified 2026-10-02).
- Capture method: https://github.com/sbOogway/sbt2/blob/main/sbt2-backend/packages/sbt2-data/src/sbt2/data/sources/bybit/api.py
- Dated path construction: https://github.com/sbOogway/sbt2/blob/main/sbt2-backend/packages/sbt2-data/src/sbt2/data/sources/bybit/source.py
- Test response fixture: https://github.com/sbOogway/sbt2/blob/main/sbt2-backend/packages/sbt2-data/tests/sources/bybit_responses.json
- Ignore rules: https://github.com/sbOogway/sbt2/blob/main/.gitignore

Assessment:
- D5: potentially useful **if** the maintainer's local daily instrument snapshots can be independently obtained with dates, hashes and coverage manifests. No such public dataset was found in the tracked repository.
- D6: insufficient as implemented for tier-history replay because only the lowest tier is embedded in the instrument snapshot; a separate full raw risk-limit response archive would be required.
- This does not change acceptance status: D5/D6 remain PARTIAL CANDIDATE EVIDENCE / NOT ACCEPTED. No contact, download of the ignored dataset, Bybit API request, collector, market-data download or PnL run was performed.


## 44. Third independent raw risk-tier capture: CandleViewer (2026-10-25)

### Source and provenance

Repository: https://github.com/CandleViewer/CandleViewer

- Fixture corpus notes: https://github.com/CandleViewer/CandleViewer/blob/a1faa8373d43b694de6c3f93ed8b765ca76038b0/packages/fixtures/bybit/README.md
- Per-file manifest: https://github.com/CandleViewer/CandleViewer/blob/a1faa8373d43b694de6c3f93ed8b765ca76038b0/packages/fixtures/bybit/2026-10-05/manifest.json
- BTC response: https://github.com/CandleViewer/CandleViewer/blob/a1faa8373d43b694de6c3f93ed8b765ca76038b0/packages/fixtures/bybit/2026-10-05/rest/risk_limit_BTCUSDT.json
- ETH response: https://github.com/CandleViewer/CandleViewer/blob/a1faa8373d43b694de6c3f93ed8b765ca76038b0/packages/fixtures/bybit/2026-10-05/rest/risk_limit_ETHUSDT.json
- Commit adding the recorded replies: https://github.com/CandleViewer/CandleViewer/commit/8e2e36bfd092d8c7331b56792dc1a00a93d9bee7

The directory is named `2026-10-05` because it is the corpus date, but the README and manifest explicitly state that these two risk-limit files were retrieved on **2026-10-25 at 18:45 UTC**. The response server timestamps are:
- BTCUSDT: `2026-10-25T18:45:35.185Z`
- ETHUSDT: `2026-10-25T18:45:35.564Z`

The project documents the capture command and implementation. It records one `GET /v5/market/risk-limit` response per symbol from public `api.bybit.com`, with `category=linear`, no key/signature/auth headers, HTTP 200 and `retCode=0` required, then redacts and checks for credential leakage. Each file contains the full REST envelope and 35 tiers; the cursor is empty. This is stronger raw-capture provenance than a derived table.

### Exact comparison with the 2026-10-21 raw capture

Compared all 35 rows and all tier fields, not just tier-1 values:

| Symbol | Oct 21 sleeve-fund | Oct 25 CandleViewer | Exact match |
|---|---:|---:|---|
| BTCUSDT | 35 tiers | 35 tiers | Yes |
| ETHUSDT | 35 tiers | 35 tiers | Yes |

The same BTC/ETH rows had already matched the 2026-09-29 `crypto-dashboard` fixture. Thus for BTCUSDT and ETHUSDT there are now three separate project repositories with matching 35-tier tables across the Sep 29, Oct 21 and Oct 25 observations. This supports consistency of those particular observed tables over this period; it does not prove no intervening change occurred.

For SOLUSDT and XRPUSDT, the exact cross-project comparison remains Sep 29 vs Oct 21 (35 tiers each). CandleViewer does not add those symbols.

### D5 check — no new instrument-spec capture

The same CandleViewer corpus includes `instruments_before.json` and `instruments_after.json`, but the manifest labels them `documented-shape (exception #1778 A)`. The README says the current corpus is built from documented shapes and existing recordings; these two instrument files are generated examples for a delisted symbol / changed tick scenario, not captured live instrument-info responses. They must not be counted as D5 historical evidence.

A targeted search for raw `GET /v5/market/instruments-info` captures found no additional qualifying instrument-spec snapshot beyond the previously identified BTCUSDT response from sleeve-fund on Oct 21. This is a bounded search result, not proof that no other public snapshot exists.

### Secondary corroboration, not a raw snapshot

A separate report in `Nguyenchitrai62/Agentic_Alpha_Lab` states that live Bybit Linear risk tiers were fetched on 2026-10-06 and frozen in a `results.json`, and prints tier-1 limit/MMR summaries for BTC, ETH, SOL, BNB and XRP:
https://github.com/Nguyenchitrai62/Agentic_Alpha_Lab/blob/21a07449f29da793f7f5296290156a3ea2f7cd3e/research/tournament/oc_utamargin/REPORT.md

The listed tier-1 values match the corresponding values in the Sep 29 crypto-dashboard fixture for those five symbols. However, the referenced raw `results.json` is not present in the inspected repository tree, and the report prints only summary fields, not full tier tables or response envelopes. Count this as secondary corroboration only; it does not add accepted raw-capture coverage.

### Updated D6 evidence map

- **Sep 29:** 9-symbol Linear tier fixture (crypto-dashboard; response result objects, common capture-start time).
- **Oct 6:** five-symbol tier-1 summary in a research report (secondary only; underlying JSON not committed).
- **Oct 15:** BTC tier table manually pasted/hand-checked in sleeve-fund (secondary only).
- **Oct 21:** raw 35-tier captures for BTC/ETH/SOL/XRP (sleeve-fund).
- **Oct 25:** raw 35-tier captures for BTC/ETH (CandleViewer).

The unique symbol coverage remains:
- Sep 29 candidate fixture: **9/47 = 19.1%**.
- Raw Oct 21 captures: **4/47 = 8.5%**.
- Raw Oct 25 captures: **2/47 = 4.3%**, both already within the four-symbol raw Oct 21 set.
- Across the raw cross-project observations, unique replicated symbols remain BTC, ETH, SOL and XRP: **4/47 = 8.5%**. The new contribution is an additional independently captured date and repository for BTC/ETH, not additional symbol breadth.

**Decision:** D6 evidence is stronger for four named symbols and spans more dates, but remains PARTIAL CANDIDATE EVIDENCE — NOT ACCEPTED. D5 remains unchanged. D4 remains partial/unverified. Do not import, forward-fill, or use these external fixtures for market-PnL replay without a separate provenance decision and authorization.


## 45. Additional D5 leads reviewed — linear candidate downgraded; spot-only capture excluded

### Hassnain2003/trading-engine — normalized two-symbol candidate, not independent raw capture

Repository file: https://github.com/Hassnain2003/trading-engine/blob/main/research/market_meta.json

The file labels itself as Bybit V5 public REST, Linear settled instruments, captured live via CCXT on 2026-10-19. It contains BTCUSDT and ETHUSDT only, with normalized values for tick size, quantity step, min/max quantities, minimum notional, price bounds, maximum leverage and funding interval. Nominal universe coverage is 2/47 (4.26%).

However:
- It is a normalized CCXT representation, not the raw Bybit response envelope; request parameters, response server timestamp, exact raw bytes and capture manifest are absent.
- The public repository has a fresh initial-public-copy commit dated 2026-11-12 with no parent history. The file's claimed 2026-10-19 capture date is therefore not independently anchored by repository history.
- Its BTC/ETH values match the corresponding normalized subset of the already inspected 2026-10-21 sleeve-fund raw response. This is consistent with a stable specification, but does not prove independent capture or establish a separate date observation.

Assessment: retain as a **low-confidence candidate / value cross-check only**, not as an independent D5 snapshot and not as accepted coverage. Do not add its 2 symbols to the independent snapshot coverage numerator.

### pranay123-stack/crypto-hft-market-making-cpp20 — genuine dated metadata, wrong product category

The repository documents real public-endpoint captures from 2026-10-18, including raw Bybit `instruments-info` response files for BTCUSDT and ETHUSDT. The saved request parameters explicitly use `category=spot`; hashes and capture procedure are documented in `tests/data/README.md`.

This is stronger provenance than a generated fixture, but it is **Spot**, while the E11/E13 research universe consists of Linear perpetuals. It therefore contributes no D5 coverage for the 47-symbol Linear universe. It may be retained as a separate Spot metadata example only.

### Decision

These leads do not improve accepted D5 Linear coverage. D5 remains PARTIAL CANDIDATE EVIDENCE / NOT ACCEPTED; D6 remains PARTIAL CANDIDATE EVIDENCE / NOT ACCEPTED; D4 remains partial/unverified. No files were imported into the research repository, no market data was downloaded, and no Bybit API, collector, PnL run or backtest was executed.


## 46. Funding formula regime change announced for 2026-11-24 onward

### Первичный источник

Bybit announcement, published 2026-11-19: [Update to Funding Rate Calculation Formula for Perpetual Contracts](https://announcements.bybit.com/en/article/update-to-funding-rate-calculation-formula-for-perpetual-contracts--art9f3b40f8766e/).

В объявлении указано:
- поэтапный rollout начинается 2026-11-24 и должен завершиться 2026-12-01;
- новая формула масштабирует базовый расчёт с 8 часов к фактическому funding interval контракта через множитель N/8;
- применённая settlement rate может измениться для контрактов с интервалом короче 8 часов;
- default funding interval и funding rate limits самим обновлением не меняются;
- таблица в announcement названа non-exhaustive, а точное расписание rollout вынесено в связанную Google Sheet.

Доступный текст связанной таблицы раскрывает лишь часть строк; отсутствие символа в видимом фрагменте не является доказательством отсутствия в полном расписании. Поэтому effective batch/date для конкретного инструмента нельзя выводить из общего announcement date или краткого списка примеров.

### Значение для D3

Нужно различать три сущности:
1. **Settlement observations:** фактически опубликованные funding rates и settlement timestamps. Они являются входом realised funding cashflow.
2. **Funding interval schedule:** effective interval каждого инструмента во времени.
3. **Funding formula regime:** effective version/formula regime и дата rollout для конкретного инструмента.

Для расчёта realised historical funding cashflow используется фактически опубликованная settlement rate; новая формула сама по себе не требует пересчитывать уже состоявшиеся settlement rates. Но для воспроизведения/объяснения режима, моделирования ожидаемого funding и forward assumptions формула и effective window должны быть зафиксированы отдельно.

Текущий API Funding History документирует rate и timestamp, но отсылает к текущему instruments-info за funding interval; историческая формула и её effective-time history в этих endpoint schemas не описаны. Источники: [Funding Rate History](https://bybit-exchange.github.io/docs/v5/market/history-fund-rate), [Instruments Info](https://bybit-exchange.github.io/docs/v5/market/instrument).

### Решение

- Добавить в будущий funding manifest поля `funding_formula_regime`, `effective_from`, `effective_to`, `announcement_ref`, `rollout_batch`, `evidence_confidence`.
- Не назначать дату rollout конкретному символу без строки из полного списка или другого первичного подтверждения.
- Не считать это доказательством пропуска funding settlements и не менять исторический PnL.
- D3 остаётся NOT ACCEPTED: по-прежнему нет реального Bybit archive с доказанной полнотой и точной settlement-mark семантикой.

Никаких API endpoints кроме отдельно разрешённого announcements endpoint не вызывалось; market data не загружались, расчёты PnL не выполнялись.


## 47. Veldra Bybit history adapter — useful acquisition-code lead, not accepted data

### Что найдено

Public repository: https://github.com/Baselm1/Veldra-Historical-Crypto-Market-Data-Downloader (MIT, version 0.1.0; source reviewed read-only on 2026-11-24).

Its Bybit adapter documents and implements:
- native Linear klines via V5 REST;
- Mark Price, Index Price and Premium Index klines via V5 REST;
- funding settlement history via V5 REST;
- public Bybit daily trade and order-book archives;
- backward pagination for klines (limit 1000) and funding (limit 200), half-open time ranges, schema/OHLC validation, normalized Parquet cache and SHA-256 of local materialization.

The docs explicitly state that Bybit's daily public archives do not publish checksum sidecars. Its REST cache hashes the normalized Parquet materialization, not the original raw HTTP response bytes. Unit tests exercise pagination, schemas and range handling, but tests do not prove live source completeness or PIT history.

### Ограничения относительно наших gates

- The adapter exposes **current market discovery/current instrument metadata**, not an effective-time archive of all past instrument spec changes or risk tiers.
- It does not reconstruct delisted/paused contract history or prove a complete PIT universe.
- Funding pagination is implemented, but the reviewed code does not independently prove that the endpoint returns every historical settlement across every interval/formula regime; completeness still requires boundary, cadence, known-case and duplicate checks.
- No historical D5/D6 archive is supplied. D4/D5/D6 therefore remain NOT ACCEPTED.
- The package requires Python >=3.14, while this repository's Research CI currently uses Python 3.11. Direct adoption would require a separately justified runtime change or a compatibility port; neither is warranted before data-path acceptance.
- A second public downloader, `gptcompany/bybit_historical_data_download`, documents Klines and Funding REST retrieval and trade/orderbook bulk archives, but its own availability report says the bulk historical download service covers trade/orderbook only. It is downloader code, not a stored accepted dataset; no evidence there closes D4–D6.

### Решение

Veldra is a **candidate implementation reference for D1/D2/D3 retrieval**, not a data source with accepted completeness. A read-only comparison with our existing repository shows no material gate-coverage advantage:
- our `bybit_downloader.py` already pages native klines, mark/index/premium klines and funding, and snapshots current instrument metadata;
- `scripts/archive_bybit_market_history.py` already has bounded funding pagination, mark/kline acquisition and page-level audit metadata;
- `funding_archive_manifest.py` stores query provenance, file hashes and an explicit unresolved settlement-schedule field;
- our separate instrument/risk modules already parse dated specs and complete risk-tier ladders, while Veldra only discovers current markets.

Veldra may be useful as a secondary code reference, but it does not remove a known missing capability. Its Python >=3.14 requirement is incompatible with our Python 3.11 Research CI. **Do not adopt or port it.** The actual bottleneck is accepted historical source evidence and authorized collection, not another downloader implementation. If collection is separately authorized later, retain our existing code as the baseline and compare only any specifically demonstrated missing behavior.

No Bybit endpoint was called, no archive or dataset was downloaded, no dependency was installed, no runner/collector was started, and no PnL calculation was run. Existing user restrictions remain unchanged.


## 48. Ограниченный BTCUSDT public-GET pilot — доступность среды не подтверждена (2026-11-25)

### Разрешение и границы

Пользователь отдельно разрешил ограниченный read-only пилот публичных GET для одного Linear-инструмента: H1 OHLCV, Mark Price, Funding History, текущие Instrument Specs и Risk Tiers. Выбран BTCUSDT, поскольку в существующем evidence inventory это наиболее полно покрытый контракт по датированным instrument/risk captures. Разрешение не включает API keys, private/account endpoints, архивную выгрузку, collector, торговлю или PnL.

### Попытка доступа

Выполнены только адресные попытки открыть публичные V5 endpoints с узкими параметрами для BTCUSDT:
- GET /v5/market/kline — H1, 2026-10-21 00:00–02:00 UTC, limit 3;
- GET /v5/market/mark-price-kline — тот же короткий интервал, limit 3;
- GET /v5/market/funding/history — тот же короткий интервал, limit 10;
- GET /v5/market/instruments-info — один символ;
- GET /v5/market/risk-limit — один символ.

Web retrieval layer вернул для kline/mark/funding/risk-limit сообщения "URL is not accessible via this tool"; для instruments-info — "403 Forbidden". Дополнительная попытка прямого HTTPS через доступную container-среду не прошла DNS resolution ("Could not resolve host: api.bybit.com"). Не получен ни один валидный Bybit JSON response; поэтому нельзя утверждать, что запросы достигли Bybit edge или что Bybit отказал в доступе.

### Результат

- API reachability: NOT VERIFIED (environment/network limitation).
- D1/D2/D3: новых наблюдений и файлов нет; gates не изменились.
- D5/D6: текущие snapshots не получены; historical effective-time coverage не проверена.
- D4 lifecycle и independent holdout period не проверялись этим пилотом.
- Нет данных, чтобы сравнить текущие instrument/risk values с прежними snapshots.

Никаких архивов/больших ответов не скачано, collector не запускался, файлы данных не создавались, зависимости и runtime не менялись, PnL не считался. Пилот остановлен на сетевом барьере; обход через сторонние прокси/зеркала не предпринимать.

### Следующее допустимое действие

Повторять те же пять точечных GET только если появится разрешённый прямой сетевой маршрут в рабочую среду или пользователь предоставит выгрузку точных публичных ответов с URL, UTC timestamp, HTTP status/headers и исходным телом. Это не расширяет разрешение на иные endpoint-ы или архивный сбор.


## 49. Повторная проверка наличия независимого holdout и готовых Bybit-путей — 2026-11-25

### Вывод

**В текущем репозитории нет доступного независимого набора, на котором можно проверить замороженный H1 Donchian(48)+EMA50/200.** Это подтверждается аудитом дерева данных, preregistration, существующего cross-venue holdout script и workflow.

### 1. Существующие OHLCV периоды не являются holdout

- В data/archives/cryptofetch/ находятся шесть Binance-style proxy ZIP; их наблюдения заканчиваются не позднее 2026-10-27.
- Эти архивы использовались в E01–E13 и при разработке/отборе последующих H1 гипотез. Они не могут быть переименованы в независимый Confirm/holdout.
- LOW_FREQUENCY_DONCHIAN48_EMA_H1_PREREGISTRATION_RU.md датирован 2026-11-04, но его Explore/Confirm folds относятся к уже изученным proxy материалам. Сам документ прямо запрещает считать CryptoFetch untouched holdout.
- В дереве текущей ветки нет data/bybit_recent, Bybit trade OHLCV, Mark candles или Funding CSV. Наличие загрузчика и workflow не означает наличие набора данных.

### 2. Старый cross-venue holdout script не закрывает задачу

scripts/run_bybit_h1_long_only_holdout.py выглядит как возможный путь, но это другой эксперимент:
- frozen list из 11 символов отобран на более раннем Binance train;
- движок использует Donchian(20), а не preregistered Donchian(48)+EMA50/200;
- каждый символ запускается отдельно с 10,000 USDT, поэтому суммарный PnL не является shared-capital portfolio curve;
- Funding cost считается верхней оценкой: положительные ставки начисляются на полный исходный notional, отрицательные receipts и уменьшение notional после TP1 игнорируются;
- Mark используется для basis diagnostics, но stop/exit остаётся на Last-price OHLC;
- сам скрипт явно предупреждает, что Bybit даты пересекаются с прежним Binance study period: это cross-venue robustness, а не последующий untouched temporal holdout.
- Скрипт требует data/bybit_recent и dated instrument/risk directories; нужных Bybit market files в текущем repo tree нет.

Следовательно, этот script нельзя просто запустить и назвать результат проверкой H1 D48+EMA или независимой временной репликацией. Его переписывание сейчас также не решит отсутствие данных.

### 3. Путь сбора в существующем workflow ограничен

.github/workflows/bybit-market-history-archive.yml:
- по умолчанию выбирает self-hosted runner;
- отдельно предупреждает, что hosted US runners блокируются Bybit;
- предлагает ubuntu-latest лишь как альтернативу, но workflow заранее ожидает блокировку по egress geography;
- перед сбором требует dated instrument snapshots.

Self-hosted runner и новые collectors остаются запрещены действующими пользовательскими ограничениями. Поэтому этот workflow не является сейчас разрешённым рабочим путём. Не менять runner, не пытаться обойти географические ограничения и не запускать workflow.

### 4. Классификация

| Условие | Статус |
|---|---|
| Замороженная H1 D48+EMA гипотеза | Есть, design frozen |
| Независимый Explore/Confirm набор | Нет |
| Независимый последующий temporal holdout | Нет |
| Bybit-native trade OHLCV D1 | Нет в repo |
| Bybit Mark D2 | Нет в repo |
| Полная Funding D3 | Нет в repo |
| Point-in-time lifecycle D4 | Не принят |
| Effective-time specs D5 | Частичные внешние snapshots, не приняты |
| Effective-time risk tiers D6 | Частичные внешние snapshots, не приняты |
| Разрешённый канал получения новых данных | Сейчас отсутствует |

### Решение

Не выбирать другие старые folds, не делать временной split внутри уже использованных архивов и не подменять независимость сменой venue при совпадающем календарном периоде. Не переписывать holdout script и не трогать workflow.

**Исследовательский статус остаётся BLOCKED BY DATA + INDEPENDENCE.** Следующее событие, которое действительно меняет статус: появление разрешённого, воспроизводимого Bybit-native набора с provenance и достаточным новым временным окном либо предоставление такого набора пользователем. После этого отдельно проверяются lifecycle, funding completeness, specs/risk effective-time и пригодность периода до любого PnL.


## 50. Повторная проверка официальных публичных источников: D1–D8 и пределы исторического покрытия (2026-11-25)

### 50.1. D1 — Linear trade OHLCV: исторический REST endpoint есть, максимальная глубина не специфицирована

Официальная документация: [Get Kline](https://bybit-exchange.github.io/docs/v5/market/kline).

- Endpoint: `GET /v5/market/kline`, категория `linear`, интервал `60` для H1.
- Можно задавать `start` и `end`; максимальный размер одной страницы — 1,000 свечей.
- Ответ отсортирован по времени открытия свечи в обратном порядке.
- Для одного инструмента и одного непрерывного года H1 это ориентировочно 8,760 строк, то есть минимум 9 страниц при лимите 1,000 (без учёта дополнительных проверочных запросов).
- Документация не устанавливает гарантированный срок хранения/максимальную историческую глубину. Наличие параметров start/end не доказывает, что любая дата доступна и что выдача полна.

**Вывод:** D1 — потенциально закрываемый публичным REST источником для ограниченного инструмента/периода. Требуются фактические raw responses, полная сетка timestamp, OHLC invariants и проверка границ. Сейчас D1 NOT ACCEPTED: данные не загружены.

### 50.2. D2 — Mark Price: исторический REST endpoint есть, но это не tick-level mark

Официальная документация: [Get Mark Price Kline](https://bybit-exchange.github.io/docs/v5/market/mark-kline).

- Endpoint: `GET /v5/market/mark-price-kline`; для Linear доступны те же H1 интервалы и start/end границы.
- Максимум — 1,000 свечей на страницу; ответ отсортирован по времени открытия.
- Это Mark Price OHLC candles, а не непрерывная история каждого изменения Mark Price внутри H1.
- Документированная максимальная глубина хранения отсутствует.

**Вывод:** D2 потенциально закрываем для H1 Mark-candle valuation при совпадающем периоде D1. Этого недостаточно для заявлений о tick-accurate liquidation или intrabar mark-trigger execution. D2 NOT ACCEPTED: фактического архива нет.

### 50.3. D3 — Funding: история settlements доступна, но пагинация и regime metadata требуют отдельного контроля

Официальная документация: [Get Funding Rate History](https://bybit-exchange.github.io/docs/v5/market/history-fund-rate).

- Endpoint: `GET /v5/market/funding/history`; для Linear обязательны category и symbol.
- Максимум — 200 settlement records на страницу.
- API отдельно предупреждает, что у символов могут быть разные funding intervals. Интервал предлагается получать через Instruments Info, то есть через текущие спецификации.
- Если передать только startTime, API возвращает ошибку; endTime без startTime возвращает до 200 событий к указанной границе; без обоих параметров — до 200 последних событий.
- Документация не обещает максимальную глубину хранения и не предоставляет effective-time историю интервалов или версий funding formula.

Для BTC с постоянным интервалом 8h ориентир составил бы около 1,095 событий в год, примерно 6 страниц при лимите 200. Это только арифметическая оценка для такого интервала, не подтверждение фактического расписания или полноты.

**Вывод:** D3 можно потенциально собрать по фактическим settlement events, но interval/formula history должны быть отдельными сущностями. Реальные опубликованные ставки нельзя пересчитывать по новой формуле задним числом. D3 NOT ACCEPTED: архива и доказательства полноты нет.

### 50.4. D4 — lifecycle/universe: публичный current endpoint не даёт историческую последовательность статусов

Официальная документация [Get Instruments Info](https://bybit-exchange.github.io/docs/v5/market/instrument) описывает запущенные инструменты и текущие статусы/поля. В схеме присутствуют статусы PreLaunch, Trading, Settling, Delivering и Closed, но endpoint не предлагает запрос состояния universe на произвольную историческую дату.

Набор текущих записей со статусом Closed не восстанавливает все прошлые переходы, intraday suspend/resume, момент фактической доступности для торговли и полный состав уже исчезнувших контрактов.

**Вывод:** D4 не закрывается разовой выгрузкой текущего instruments-info. Нужны датированные последовательные наблюдения/первичные listing-delisting announcements и доказуемая реконструкция переходов. D4 PARTIAL / NOT ACCEPTED.

### 50.5. D5 — instrument specs: известны текущие значения и некоторые периодические изменения, но не вся effective-time история

Документация Instruments Info прямо предупреждает, что maxLimitOrderQty, maxMarketOrderQty и postOnlyMaxLimitOrderSize корректируются дважды в месяц — 3-го и 17-го числа в 08:00 UTC+8. Это доказывает, что некоторые параметры изменяются по расписанию; оно не даёт всех прошлых значений и не заменяет историю tickSize, qtyStep, minNotional и остальных execution filters по каждому символу.

**Вывод:** регулярный snapshot может накапливать будущую историю, но не восстанавливает автоматически прошлое. Известные сторонние snapshots остаются частичными и не принимаются. D5 PARTIAL CANDIDATE EVIDENCE / NOT ACCEPTED.

### 50.6. D6 — risk tiers: endpoint возвращает текущую таблицу, не архив effective-time

Официальная документация [Get Risk Limit](https://bybit-exchange.github.io/docs/v5/market/risk-limit) описывает текущие таблицы risk limits; для Linear выдаётся 15 символов на страницу с cursor pagination. В ответе есть tier IDs, position limits, initial/maintenance margin и max leverage, но endpoint не документирует исторический запрос tier table на дату.

Кроме того, исторический account-applied tier зависит от позиции/активных ордеров и состояния аккаунта; публичная таблица биржи сама по себе не восстанавливает индивидуальный applied tier.

**Вывод:** D6 можно регулярно фиксировать вперёд для будущего времени, но нельзя считать текущую таблицу исторической. D6 PARTIAL CANDIDATE EVIDENCE / NOT ACCEPTED.

### 50.7. D7 — архивные сделки: официальный lead найден, но не доказан как полноценный L2 источник

В официальной документации [Get Recent Public Trades](https://bybit-exchange.github.io/docs/v5/market/recent-trade) прямо сказано, что архивные исторические сделки можно скачать с сайта Bybit. Endpoint recent-trade сам по себе возвращает ограниченную страницу, максимум 1,000 записей для контрактных категорий.

Официальная страница [Historical data download](https://www.bybit.com/en/derivative-activity/history-data) открывается и показывает каталог Data products, но доступный текстовый просмотр не раскрывает inventory конкретных файлов, глубину дат, символы, частоту или контрольные суммы.

Следовательно:
- официальный lead на архив исторических сделок существует;
- это потенциальный материал для самостоятельной агрегации trade OHLCV, только если будут подтверждены полнота, timestamps, coverage и отсутствие пропущенных файлов;
- наличие trade archive не доказывает наличие Mark Price, Funding settlements, L2 snapshots/deltas или очереди заявок;
- maker fill / queue replay на основании одного trade archive не принимается.

**Вывод:** D7 остаётся DEFERRED / NOT ACCEPTED. Не скачивать архив и не собирать данные без отдельного разрешения.

### 50.8. D8 — fees: публичный fee-group endpoint не является историческим retail fee schedule

Официальная документация [Get Fee Group Structure](https://bybit-exchange.github.io/docs/v5/market/fee-group-info) описывает групповые ставки Pro-level и Market Maker; документация отдельно говорит, что новый grouped fee structure не применяется к retail traders. В ответе есть updateTime, то есть timestamp последнего обновления доступной структуры, а не архив всех прошлых ставок.

Публичная текущая ставка не доказывает историческую ставку конкретного аккаунта. Для исследовательского taker-only сценария можно заранее задать консервативную явно маркированную базовую ставку и stress cases, если это разрешено спецификацией эксперимента; такой сценарий не следует выдавать за фактическую историческую комиссию пользователя. Для maker claims D7 и отдельное подтверждение fee/fill assumptions остаются обязательными.

**Вывод:** D8 может быть ограничен прозрачным fee scenario для исследовательского расчёта, но фактическая историческая retail/account fee series не установлена. D8 NOT ACCEPTED как исторический источник.

### 50.9. Независимый период и реальный путь закрытия блокера

- CryptoFetch proxy заканчивается не позднее 2026-10-27 и уже использован в E01–E13; никакой новый split внутри этого архива не становится независимым.
- OKX archive, который ранее был проверен, имеет лишь около 29 дней после конца CryptoFetch на дату этого аудита. Это не создаёт независимый годовой holdout; venue change при совпадающем календарном периоде — cross-venue robustness, а не untouched temporal replication.
- Новый будущий период может стать независимым только после заморозки гипотезы, правил и критериев и при условии, что сбор данных будет отдельно разрешён и воспроизводимо зафиксирован. Одного факта, что календарная дата позже 2026-10-27, недостаточно: нужно заранее определить длительность/достаточность выборки и не смотреть outcomes до завершения Confirm.
- Официальный архив сделок — lead для последующего read-only review интерфейса и метаданных, но не готовый substitute для D1–D6.
- Существующий user authorization scope не расширяется этим аудитом: никаких новых Bybit API calls, скачивания market archives, запуска collectors/workflows или PnL/backtests.

### Итоговая матрица

| Gate | Что реально существует публично | Что остаётся неизвестным/непринятым | Статус |
|---|---|---|---|
| D1 OHLCV | Historical REST candles, 1,000/page | Retention/completeness, raw archive | NOT ACCEPTED |
| D2 Mark | Historical Mark candles, 1,000/page | Retention/completeness, intrabar mark | NOT ACCEPTED |
| D3 Funding | Historical settlement events, 200/page | Full history, historical interval/formula regime | NOT ACCEPTED |
| D4 Lifecycle | Current instrument statuses | Full PIT transitions/universe | PARTIAL / NOT ACCEPTED |
| D5 Specs | Current specs, known scheduled field updates | Full per-symbol effective-time history | PARTIAL / NOT ACCEPTED |
| D6 Risk tiers | Current paginated risk tables | Historical tiers and account-applied tier | PARTIAL / NOT ACCEPTED |
| D7 Trades/L2 | Official archived-trades lead | File coverage, L2/sequence/queue history | DEFERRED / NOT ACCEPTED |
| D8 Fees | Current grouped Pro/MM fee information | Historical retail/account-specific fees | NOT ACCEPTED |

**Решение:** не писать ещё один downloader и не переписывать runner. Основной технический вопрос теперь не «можем ли мы вызвать API», а «есть ли разрешённый, достаточно полный, воспроизводимый и независимый исторический период». Исследовательский статус остаётся **BLOCKED BY DATA + INDEPENDENCE**.


## 51. Bybit official announcements as point-in-time evidence for D4–D6 (2026-11-25)

### 51.1. D4 — listing/delisting announcements provide dated lifecycle events

Read-only search of official Bybit announcements found repeatable primary-source event types:

- New listings specify that trading is open and often include symbol, product category, settlement asset, initial tick size, maximum leverage, capped funding rate and funding interval. Example: CPUSDT Linear perpetual listing dated 2026-09-04, trading open, tick size 0.00001, max leverage 20, capped funding 2.5%, funding interval 4h.
- Delisting announcements specify exact UTC delisting time and confirm trading ceases. Examples: SCUSDT 2026-06-11 09:00 UTC; ASPUSDT 2026-09-05 09:00 UTC; TMXUSDT 2026-10-30 09:00 UTC; AGIUSDT 2026-11-13 09:00 UTC.
- Multi-asset migrations/rebrands can delist several perpetual symbols in one notice. Example: IPUSDT and IPUSDC delisted 2026-06-26 07:00 UTC; TON perpetual pairs delisted 2026-06-15 09:00 UTC.
- Some corporate-action/contract-size announcements include explicit intraday trading halt windows and resume windows, including funding settlements skipped during the halt. Such events must be represented as temporary trading availability interruptions, not ordinary candle gaps.

This is materially useful for PIT lifecycle: announcements can establish explicit listing/delisting effective timestamps and known halt windows for named symbols. However, search results and a sample of notices do not prove that the announcement archive is complete for all historical symbols, all suspension/resume events, or all categories. A notice can also cover Spot and Perpetual separately; product category must be parsed, never inferred from token name.

**D4 status:** PARTIAL, with a stronger primary-source event reconstruction path. Not accepted until a systematic archive inventory, symbol-level coverage reconciliation, and conflict/absence policy are implemented. Current instruments-info snapshots remain corroboration, not a substitute.

### 51.2. D5 — dated announcements contain several useful spec-change fields

Official announcements expose at least these effective-time changes in structured text:

- Tick size: current and new tick size plus effective UTC time. Examples: broad USDT Perpetual change on 2026-11-20 07:30 UTC; another batch 2026-10-12 07:30 UTC; another 2026-08-11 08:30 UTC.
- Maximum order size: before/after market and limit order sizes in coin units plus effective UTC time. Examples: SOXXUSDT and SNDKUSDT on 2026-11-20 12:30 UTC; another batch on 2026-11-05 05:31 UTC.
- Listing-time initial specifications: tick size, max leverage, capped funding rate and funding interval for the new contract.
- Contract-size/corporate-action adjustments can include old/new conversion ratios, pause window, trading resume window, and whether funding settlements are skipped during the pause.

This can reconstruct selected changes in `tickSize`, `maxMarketOrderSize`, `maxLimitOrderSize`, selected initial leverage/funding parameters, and contract multiplier/size conversion where explicitly stated.

It does **not** reconstruct a complete historical spec vector for every symbol: minOrderQty, qtyStep, minNotional, price bounds, every leverage step, every contract multiplier change and all effective-time corrections are not guaranteed to appear in every announcement. A listing announcement is an initial snapshot, not proof that parameters stayed unchanged until the next discovered notice.

**D5 status:** PARTIAL, with a practical primary-source event ledger path for fields explicitly announced. Not accepted as complete execution-spec history.

### 51.3. D6 — risk-limit announcements prove dated changes, but often not full tier ladders

Official examples show two levels of detail:

1. Some announcements provide current and after-adjustment maximum leverage per symbol (e.g. selected perpetuals effective 2026-09-11 08:00 UTC).
2. Other announcements only name affected symbols, state effective time, and link to a generic/current risk-limit rules page. Some notices describe account buffer periods and automatic application timing.

The official Help Center explains that risk-limit changes can affect IMR, MMR, maximum leverage and position limits, and that tier can change dynamically as position value changes with Mark Price. This means a dated max-leverage change is not equivalent to a full historical tier table or an account-applied tier observation.

**D6 status:** PARTIAL. Announcements can timestamp selected risk parameter changes and identify affected symbols, but cannot by themselves reconstruct every tier's notional ceiling/MMR/IMR values or the user's account-applied tier. Do not infer the missing table from a current endpoint.

### 51.4. Proposed event-ledger schema and confidence rules

A future offline parser/inventory should normalize each official notice into append-only event records:

- `event_id`, `announcement_url`, `announcement_title`, `published_at_utc`, `source_language`, `retrieved_at_utc`, `raw_html_sha256` (only if captured later under an authorized collection step);
- `category` (linear/spot/inverse/option/TradFi), `symbol`, `event_type` (LIST, DELIST, TRADING_HALT, RESUME, TICK_CHANGE, ORDER_SIZE_CHANGE, RISK_LIMIT_CHANGE, CONTRACT_SIZE_CHANGE, FUNDING_RULE_CHANGE);
- `effective_from_utc`, `effective_to_utc` (nullable), `before_values`, `after_values`, `unit`, `explicitness`;
- `source_evidence` (exact notice section/table row), `confidence`, `supersedes_event_id`, `notes`.

Rules:
1. Preserve the published notice date separately from the effective timestamp.
2. A missing field is unknown, never zero and never inherited from a modern API response without a dated observation.
3. Keep notices and API snapshots as separate evidence types; use snapshots to corroborate, not silently fill historical gaps.
4. Conflicting notices remain unresolved until a later explicit correction is found.
5. Announced max leverage must not be promoted into a full D6 tier ladder.
6. Product type must be explicit; TradFi perpetuals, Spot, inverse and linear crypto perpetuals must not be mixed.
7. A search miss is not proof that no announcement existed. Coverage requires pagination/archive inventory and reconciliation against all symbols in the research universe.

### 51.5. Research decision

Official announcements are a credible route to improve D4 and selected D5/D6 fields. The route is more promising than relying only on current Instruments Info/Risk Limit endpoints or importing unanchored third-party snapshots.

However, this is a source-capability review, not an accepted historical dataset. The current search was targeted and sampled, not a full systematic crawl; no notices were downloaded into the repository, no event records were generated, no API or archive collector was run, and no gate status changes to ACCEPTED.

**Next permissible research step:** design a bounded offline announcement inventory for the frozen 47-symbol Linear universe, beginning with D4 listing/delisting and D5 tick-size/order-size events, then D6 risk notices. Before any automated collection or raw archive capture, confirm that its network/source-access scope is separately authorized. Until then, keep all D4–D6 gates PARTIAL / NOT ACCEPTED.


## 52. Bounded announcement-to-universe coverage spot check (2026-11-25)

### 52.1. Exact denominator recovered from the original E11 artifact

The original existing GitHub Actions artifact E11, run `41361376448`, artifact `13105661683` (`e11-h1-shared-capital-portfolio.zip`), was read to recover `e11_h1_shared_capital_universe_manifest.csv`. This was an already-existing research-result artifact, not a market-data archive. The manifest contains 50 rows: 47 included symbols and three exclusions (AEROUSDT, GRAMUSDT, HYPEUSDT), each excluded because one or more folds had fewer than 100 bars.

The exact 47 included symbols are:

`AAVEUSDT, ADAUSDT, ALGOUSDT, APTUSDT, ARBUSDT, ASTERUSDT, ATOMUSDT, AVAXUSDT, BCHUSDT, BNBUSDT, BTCUSDT, CAKEUSDT, DASHUSDT, DOGEUSDT, DOTUSDT, ENAUSDT, ETCUSDT, ETHUSDT, GMXUSDT, HBARUSDT, ICPUSDT, JSTUSDT, LINKUSDT, LTCUSDT, MINAUSDT, MORPHOUSDT, NEARUSDT, ONDOUSDT, PAXGUSDT, PEPEUSDT, POLUSDT, PUMPUSDT, QNTUSDT, RAYUSDT, RENDERUSDT, SHIBUSDT, SKYUSDT, SOLUSDT, SUIUSDT, TAOUSDT, TRXUSDT, UNIUSDT, WLDUSDT, WLFIUSDT, XLMUSDT, XRPUSDT, ZECUSDT`.

**Denominator warning:** this is the E11/E13 Binance-style proxy sample selected for common fold history, not a Bybit Linear historical universe. It is fixed and survivor-biased. The three exclusions are not evidence that those contracts did not exist on Bybit; conversely, matching tickers do not prove continuous Bybit listing/tradability.

### 52.2. Search method and boundary

A bounded, manual, indexed-web search was run against official `announcements.bybit.com` pages for the exact 47-symbol set. Queries covered listing/delisting/suspension terms and the D5/D6 event families. Several specific dated notices were opened/read. This was **not** a page-by-page crawl of the official archive, not a full-pagination inventory, and not a raw HTML capture. Search-engine misses are recorded only as “no hit surfaced in this sample”; they are not recorded as “no event existed”. Product category was checked before counting an event; Spot, TradFi/stock and unrelated loan-program notices are not treated as Linear crypto-perpetual evidence.

### 52.3. D5 — dated spec-change hits in the sampled notices

- Tick-size notices surfaced hits for **10 / 47** symbols: Aug 11, 2026 — ATOMUSDT, CAKEUSDT, MORPHOUSDT, NEARUSDT, RENDERUSDT, TRXUSDT, XLMUSDT; Oct 12, 2026 — PAXGUSDT, BNBUSDT, BCHUSDT, CAKEUSDT, MORPHOUSDT. The union is 10 symbols.
- Max-order-size notices surfaced one matching symbol in the sampled notices: Nov 5, 2026 — WLDUSDT. The reviewed Nov 9 and Nov 20, 2026 tables had no symbol from the 47-symbol sample.
- Combined D5 hit set in this bounded sample: **11 / 47 (23.4%)**. This is a lower-bound count of positive matches in selected notices, not a coverage estimate for the full Bybit archive. No evidence was established for all qtyStep, minQty, minNotional, price bounds, contract multiplier or every historical change.

Primary sources: [Aug 11 tick-size notice](https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-aug-11-2026--art4f47b6648755/); [Oct 12 tick-size notice](https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-oct-12-2026--art5c4a8b8eef37/); [Nov 5 max-order-size notice](https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-nov-5-2026--artff0e2f730786/); [Nov 9 max-order-size notice](https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-nov-9-2026--art30ea1bf8d3b1/); [Nov 20 max-order-size notice](https://announcements.bybit.com/en/article/changes-of-max-order-size-for-usdt-perpetual-contracts-nov-20-2026--arte1da2b0316fa/); [Nov 20 tick-size notice](https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-nov-20-2026--art2a243e629ca8/); [Jun 5 tick-size notice](https://announcements.bybit.com/en/article/change-tick-size-for-usdt-perpetual-contract-jun-5-2026-blt539f4749d220f97b/).

### 52.4. D6 — risk-limit hits in the sampled notices

The sampled Linear-perpetual risk-limit notices surfaced hits for **19 / 47** unique symbols:

- Apr 28, 2026: POLUSDT, ALGOUSDT, ICPUSDT, ONDOUSDT, MINAUSDT.
- Jun 12, 2026: PAXGUSDT.
- Jul 8, 2026: RENDERUSDT, CAKEUSDT, DASHUSDT.
- Sep 4, 2026: AVAXUSDT, XLMUSDT, LTCUSDT, BCHUSDT, UNIUSDT, DOTUSDT, ETCUSDT, ICPUSDT, ALGOUSDT, DASHUSDT, QNTUSDT, JSTUSDT, NEARUSDT.

The union is **19 / 47 (40.4%)**. This counts symbols named in dated risk-limit notices, not full tier-history coverage. Where a notice provides only a change to maximum leverage or an affected-symbol list, it does not reconstruct every tier, maintenance-margin rate, position-value boundary, or account-applied tier. Sep 11 and Aug 21 examples returned by the search concern TradFi/stock contracts and were excluded from Linear crypto counts.

Primary sources: [Apr 28 risk-limit notice](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-polusdt-algousdt-apr-28-2026--blt57993cb6d157988e/); [Jun 12 risk-limit notice](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-paxgusdt-galausdt-jun-12-2026--blt366cf2f185d6d505/); [Jul 8 risk-limit notice](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-blurusdt-fartcoinusdt-jul-8-2026--blt22544b85ab5016cf/); [Sep 4 risk-limit notice](https://announcements.bybit.com/en/article/risk-limit-adjustment-for-selected-perpetual-contracts-avaxusdt-xlmusdt-sep-4-2026--art453915b9e8fd/).

### 52.5. D4 — listing/delisting/lifecycle result

The batched symbol searches for listing, delisting and trading-suspension terms did not surface a confirmed D4 notice naming one of the 47 sample symbols. This is **zero confirmed hits surfaced in this bounded search**, not 0/47 archive coverage and not evidence that no listing/delisting/suspension event occurred. Earlier sampled D4 notices for SCUSDT, ASPUSDT, TMXUSDT and AGIUSDT, and the CPUSDT listing, are outside this 47-symbol sample. D4 therefore remains unmeasured by this spot check.

### 52.6. Coverage summary and decision

| Stream | Unique symbols with a positive match in sampled notices | Interpretation |
|---|---:|---|
| D4 lifecycle | 0 surfaced | Search sample only; no absence inference |
| D5 selected tick/order-size changes | 11 / 47 (23.4%) | Partial event evidence, not complete spec history |
| D6 selected risk-limit changes | 19 / 47 (40.4%) | Partial event evidence, not full tier history |
| D5 ∪ D6 | 24 / 47 (51.1%) | 23 symbols had no positive hit in the notices sampled; unknown whether archive contains events for them |

The 24/47 union is not a “51.1% archive completeness” metric. It only describes distinct sample symbols named by at least one selected D5/D6 notice. A systematic archive inventory still requires official archive pagination/category reconciliation, symbol-by-symbol event ledger, exact source URLs and publication/effective timestamps, and a complete denominator that is genuinely Bybit Linear rather than a survivor-biased proxy sample.

**Decision:** no D4/D5/D6 gate is accepted or upgraded. No market data, Bybit API endpoints, automated collectors, raw announcement pages, PnL, backtests, sweeps or event studies were run. Only the already-existing E11 result artifact was read to recover its manifest; public announcement pages/search results were inspected without raw capture. The next useful step is to design the archive-pagination and reconciliation protocol, but automated crawling/raw capture remains outside the present authorization scope.


## 53. Official announcement archive pagination and reconciliation design (2026-11-25)

### 53.1. Public archive structure observed

The official Bybit announcement site exposes category pages with 20 items per page. On the pages opened on 2026-11-25, the visible pagination totals were:

| Archive route | Pages observed | Approx. listed items at 20/page | Intended event use |
|---|---:|---:|---|
| [New crypto / listings](https://announcements.bybit.com/en/?category=new_crypto) | 25 | up to 500 | D4 listing/open events; page contains mixed Spot, Derivatives, Options and TradFi entries, so product filter/category parsing is mandatory |
| [Delistings](https://announcements.bybit.com/en/?category=delistings) | 11 | up to 220 | D4 delisting/last-trade events; mixed token and contract delistings must be separated |
| [Maintenance Updates](https://announcements.bybit.com/en/?category=maintenance_updates) | 19 | up to 380 | D4 temporary suspensions/resumes and contract adjustments; also useful for corporate actions |
| [Latest Bybit News](https://announcements.bybit.com/en/?category=latest_bybit_news) | 11 | up to 220 | D5 tick/order-size and some D6 risk notices; category is mixed and needs event-type parsing |

These are page totals visible at the time of inspection, not a stable API contract or a verified historical archive inventory. Some event families appear under more than one category, and a category can include unrelated product types. Therefore the counts cannot simply be added as unique notice counts. A broad mixed archive route showed 98 pages but was not used as the event-family denominator because it mixes unrelated announcement categories.

### 53.2. Minimal reconciliation protocol (design only; not executed)

1. Freeze the target window and target universe version before reviewing pages. Preserve the E11 47-symbol proxy sample as a clearly labelled comparison set; do not rename it Bybit PIT universe.
2. Enumerate every page for the four relevant archive routes above, record page number, observed total pages, retrieval time and visible item count. Recheck pagination at the end because the archive is dynamic.
3. Deduplicate notices by canonical announcement URL / article slug across categories. Preserve category membership as a set rather than dropping duplicates.
4. Extract candidate symbols from title and article body, then classify product category explicitly: Linear crypto perpetual, Inverse, Spot, Options, TradFi/stock, token-only, or unknown. Only matching Linear crypto-perpetual events count for this research scope.
5. Classify event type: LIST/OPEN, DELIST/LAST_TRADE, HALT, RESUME, TICK_CHANGE, ORDER_SIZE_CHANGE, CONTRACT_SIZE_CHANGE, RISK_LIMIT_CHANGE, FUNDING_RULE_CHANGE, or OTHER. Do not treat a network deposit/withdrawal suspension as a trading halt.
6. Store publication time and effective time separately. For ranges/windows, store both start and end. Keep before/after values and units exactly as announced; do not infer missing values from current Instruments Info or Risk Limit endpoints.
7. Reconcile each symbol against all pages and categories. Use explicit statuses: `hit`, `no_hit_after_complete_inventory`, `not_in_scope_product_type`, `ambiguous_symbol_or_product`, `page_not_retrieved`, `article_unavailable`. Never collapse a failed/missing page into a no-hit result.
8. Independently check that page enumeration is complete: expected page numbers are contiguous, last-page item count is plausible, duplicate URLs are accounted for, and the visible total-page count is unchanged or rechecked. A search-engine query can help discover articles but cannot replace page enumeration.
9. Only after a separate authorization for automated collection/raw capture: preserve exact HTML response bytes, canonical URL, retrieval timestamp, HTTP metadata where available, and SHA-256; then parse into the event ledger. Until then, this remains a design and manual read-only research protocol.

### 53.3. Decision

The public site is paginated enough to make a bounded inventory tractable in principle, but the current search did not execute this protocol and does not establish archive completeness. The next concrete decision is whether to authorize a read-only, automated crawl of only these public announcement category pages and linked public article pages, with no Bybit market API calls, no account endpoints, no orders and no raw market-data downloads. Without that separate authorization, do not implement or dispatch a crawler. D4/D5/D6 remain PARTIAL / NOT ACCEPTED.


## 54. Read-only public announcement inventory collector (implementation and execution, 2026-11-25)

### 54.1. Scope and controls

Added `scripts/collect_bybit_announcements.py`, offline tests `tests/test_collect_bybit_announcements.py`, and workflow `.github/workflows/bybit-announcement-archive-inventory.yml` on the research branch. The workflow uses GitHub-hosted `ubuntu-latest`, not self-hosted runners. The collector is restricted to HTTPS host `announcements.bybit.com`; redirects to any other host are rejected. It issues GET requests only to the four agreed public archive categories and linked article pages. It has no credentials, cookies, API keys, market/account endpoints, trading actions, proxy or alternate host. Minimum request delay is 1 second in the workflow; each response is capped at 8 MiB; timeouts and page/article failures are recorded. Output must be a new/empty directory, preventing accidental overwrite.

For every captured HTML page it records canonical URL, retrieval timestamp UTC, HTTP status, selected response headers, byte count, SHA-256 and relative file path. Inventory JSON links category page captures, unique article captures, symbol matches and failure records. The collector is a discovery/inventory aid: its regex classification fields are explicitly candidates and must be manually reviewed before an event is promoted into the D4/D5/D6 ledger.

### 54.2. Fail-closed improvements

The archive pagination totals observed on 2026-11-25 are encoded as baselines (25, 11, 19, 11 pages for the four selected categories). A mismatch between parsed pagination and that observed baseline aborts that category rather than allowing a false completeness claim. Linear candidates require explicit USDT/USDC perpetual or Linear wording; inverse, TradFi and generic ambiguous perpetuals are separated. This is still not a guarantee that the site exposes every archive item: pagination baselines must be revalidated against the live site, and full-page inventory must be independently reconciled.

### 54.3. CI and collection status at documentation time

The offline parser/safety tests passed in the initial workflow attempts, including the corrected run. A first collection workflow run `45584843911` (code SHA `3188d6d96b12201b822e53d41ef6331d5a76df8c`) remained in progress at last check, with the live collection step active and no artifact available yet. A second run `45585129324` was triggered after fail-closed pagination/product classification improvements (code SHA `bfb5c21ca2748f198856f011cddff2b7579f98b4`); its offline tests passed and its collection step was also in progress at last check. Neither run had produced a completed inventory artifact at that point. The earlier run used the initial collector revision and must not be treated as accepted evidence; the second run is the intended strict run.

### 54.4. Acceptance boundary

No archive completeness claim, event-study input, backtest or PnL is accepted from an in-progress workflow. Even after a successful run, inventory completion only means the selected pages/articles were retrievable under this protocol; it does not prove the announcements site itself is historically exhaustive or that regex candidate classifications are correct. D4/D5/D6 remain PARTIAL / NOT ACCEPTED until captured records are reviewed, reconciled to a genuine Bybit Linear point-in-time universe, and effective-time fields are evidenced. The workflow does not query Bybit market APIs or collect market data.


## 55. Collector live-HTML validation and invalidation of the first “success” (2026-11-25)

### 55.1. Important correction: first run was a false-complete result

Workflow run `45584843911` finished SUCCESS, but inspection of its artifact `15008282616` showed that the collector had parsed only page 1 from each category: 1/1 pages per category, 80 unique article pages total (20 per category), and marked `complete=true`. The real captured Bybit HTML visibly contains pagination list items with numeric `title` attributes (for example pages 1, 2, 3, 4, 5, 25) rather than ordinary page-number hrefs, and article links use `/en/article/.../?category=...`. The first parser missed both structures. Therefore this run is **INVALID / NOT ACCEPTED**, despite GitHub Actions reporting success. Its 80-article artifact must not be used for coverage counts or event records.

### 55.2. Strict-pagination parser correction

Updated the parser to read numeric `li.ant-pagination-item[title]` values and accept actual `/en/article/...` paths. A live-page HTML inspection confirmed the observed New Listings page exposes 25 as the last pagination item and 20 article links. The other categories use the same markup family. The strict 25/11/19/11 baseline now fails closed if the parsed last page differs.

### 55.3. Article-content extraction correction

The first article classifier used all visible page text, including global navigation/footer text. This could contaminate product/event classification (for example a generic site-wide “TradFi” or “delist” string could be mistaken for article content). The collector now extracts `props.pageProps.articleDetail` from the page's `__NEXT_DATA__` JSON and uses only the article's structured `title`, `date`, `categoryConnection`, and `content_html`. Candidate symbol matching and event/product classification run on article title/body only; raw HTML remains preserved. Offline regression tests now verify the structured body excludes unrelated page chrome. Classification is still a candidate for manual review, not an accepted ledger record.

### 55.4. CI state at this update

- Run `45585129324`: strict-pagination version correctly failed closed because the parser still did not read numeric pagination list-item titles; artifact records four explicit pagination mismatches. This is a useful fail-closed result, not an accepted inventory.
- Run `45585145736`: same pagination failure on the next code revision; not accepted.
- Run `45585616214`: failed offline tests due a syntax error in the first attempt to quote the embedded JSON regex; collection was skipped. Fixed immediately.
- Run `45585668574`: latest revision with structured article extraction and the new regression test; offline tests passed, public collection step was in progress at last check. This is the intended strict run to inspect when complete.
- Earlier runs `45585362357`, `45585379582`, `45585495358`, and `45585646168` were started from intermediate revisions. Their artifacts/results must be inspected but cannot supersede the latest code; none is accepted merely because a workflow returns success.

### 55.5. Acceptance rule

Only an artifact produced by the latest code revision, with all four category page sequences complete, all discovered article pages captured, zero retrieval/parsing failures, and manually reviewed article classifications can support an event ledger. Any run with a different code SHA, incomplete page inventory, parser mismatch, or candidate-only classifications remains diagnostic. D4/D5/D6 stay PARTIAL / NOT ACCEPTED. No market data, account API, trading, PnL or backtest was involved.
