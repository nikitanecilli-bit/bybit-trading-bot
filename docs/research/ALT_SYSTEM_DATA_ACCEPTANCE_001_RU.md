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
| D7 L2/trades | `missing` для репрезентативного execution dataset | Один малый AAVEUSDT sample не является достаточным набором |
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
