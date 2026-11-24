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

### 11.4. Acceptance decision

| Requirement | Current decision after this checkpoint |
|---|---|
| D1 Bybit-native OHLCV | `missing` in repository; Hugging Face lead is `unverified` |
| D2 Bybit Mark | `missing/unverified` in repository; external leads are `unverified` |
| D3 Funding + settlements | `missing/unverified` in repository; external leads are `unverified`; settlement completeness not established |
| D4 PIT universe/lifecycle | `missing/unverified`; delisted-symbol inclusion claims do not prove full PIT transitions |
| D5 Effective-time instrument specs | `missing` |
| D6 Effective-time risk tiers | `missing` |
| D7 Representative trades/L2 | `missing`; only one old, non-retained AAVE diagnostic is evidenced |
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
- Risk-tier snapshots paginate the returned symbol/tier rows, validate tier structure and monotonic relationships, and record fetch time/page provenance. `RiskTierHistory.get_tier(s)()` selects the newest snapshot no later than the requested timestamp and can fail closed on missing or stale coverage.
- The same temporal limitation applies: the endpoint snapshot records the observed tier table at capture time, not an authoritative historical effective-time change log. It cannot reconstruct pre-capture tier changes.
- No dated risk-tier snapshot series is currently committed. D6 remains `missing` for the historical interval under consideration.

**Operational implication:** the existing collectors can begin building a forward-dated evidence trail only after an explicit future authorization and successful capture. Their presence in GitHub does not create historical PIT data retroactively. Since the current workflows are manual-only and the user hold prohibits runner setup/dispatch, no new snapshots can be assumed or scheduled in this project state.
