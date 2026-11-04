# ALT-SYSTEM-ACCOUNTING-CONTRACT-AUDIT-001 — static review

Дата: 2026-11-05  
Ветка: `research/market-regime-v1-main`  
Режим: read-only source/test/documentation review; никаких рыночных данных или PnL replay не использовано.

## Краткое решение

- **Подтверждённого нового profit-inflating дефекта в проверенных формулах не найдено.**
- **Instrument specs: кодовая валидация сильная, историческая effective-time полнота не доказана.**
- **Risk tiers: ladder/IM/MM формулы и structural checks согласованы, но historical completeness/effective-time не доказаны.**
- **Funding: cashflow sign/partial-close/boundary logic покрыты deterministic tests; settlement Mark остаётся H1 Mark-candle proxy, а расписание имеет неустранимую по текущим snapshot evidence неоднозначность при смене интервала.**
- **Portfolio: предыдущий audit и regressions закрывают ряд accounting invariants; это не account-wide Bybit UTA/cross-margin/liquidation model.**

Никакие статусы BLOCKED из readiness decision не снимаются.

## 1. Instrument specs

Проверено:
- `bybit_instrument_specs.py`
- `instrument_spec_history.py`
- `scripts/snapshot_bybit_instruments.py`
- `tests/test_bybit_instrument_specs.py`
- `tests/test_instrument_spec_history.py`

### Подтверждённые защитные свойства

- Decimal parsing отвергает missing/non-finite/non-positive обязательные значения.
- Поддерживается только linear category; обязательны symbol/category, priceFilter, lotSizeFilter; optional leverageFilter не подменяется дефолтами.
- Проверяются min/max price, qty limits, leverage bounds; limit price rounding направлено наружу (buy вниз, sell вверх), quantity округляется вниз.
- `validate_order` проверяет Trading status, min qty, max limit/market qty, min notional; limit price проверяется на price range и tick alignment.
- История отвергает duplicate timestamps, schema/source/category mismatch, duplicate symbols, malformed rows, invalid timezone/sub-ms timestamps и symbol identity reuse.
- As-of selection выбирает только последний snapshot, fetched_at которого не позже requested timestamp; staleness можно ограничить max_age.
- При наличии page observations проверяются последовательность страниц, status filters, continuation flags, row counts, collection window и соответствие символов.

### Остаточные ограничения

1. **fetched_at — время наблюдения/завершения сбора, не exchange effective_from.** As-of lookup корректно не использует будущий snapshot, но не доказывает, что изменённый tick/qty/minNotional/status вступил в силу ровно в fetched_at.
2. Сбор full universe — последовательность нескольких status-filter/page requests. Page evidence подтверждает ход сбора, но не создаёт атомарный биржевой snapshot; состояние инструмента может измениться в процессе обхода.
3. Runtime loader допускает legacy snapshot без `page_observations`. Такой файл может пройти structural checks, но сам по себе не имеет проверяемого page-completeness evidence. Для data acceptance его нельзя приравнивать к fully attested snapshot.
4. Возможное переименование symbol маркируется как `possible_rename_not_proven`; автоматического склеивания истории нет — это безопасное поведение.
5. Даже свежие snapshots не дают полноценного исторического effective-time журнала. Текущий data acceptance D5 остаётся PARTIAL/UNVERIFIED.

**Решение:** parser/rounding contract — статически согласован; историческая PIT спецификация и полное покрытие — BLOCKED.

## 2. Risk tiers и margin

Проверено:
- `bybit_risk_tiers.py`
- `scripts/snapshot_bybit_risk_limits.py`
- `tests/test_bybit_risk_tiers.py`
- `scripts/audit_instrument_snapshot_coverage.py` (joint instrument/risk state path)

### Подтверждённые защитные свойства

- Collector валидирует source response, cursor type/repetition, duplicate/conflicting tier rows, positive numeric values, lowest-tier marker, monotonic risk limits/MMR/IMR/max leverage и mmDeduction recurrence.
- Runtime loader повторно валидирует tier ladder, timestamp/schema/source/category, tier ids, duplicate limits, exactly one lowest tier и recurrence.
- При наличии page observations сверяются последовательность страниц, request chronology, continuation flags, symbol coverage и total tier count.
- As-of lookup не использует future snapshot; max_age поддерживается.
- Tier выбирается как первый riskLimitValue, покрывающий position value; max leverage проверяется для выбранного tier.
- Position-level формулы соответствуют задокументированной модели: IM = position value / configured leverage; MM = position value × MMR − mmDeduction.
- Отдельный `get_tiers` возвращает полную ladder без entry leverage rejection, чтобы уже открытая позиция могла быть проверена на maintenance shortfall, если позднее tier max leverage снизился.

### Остаточные ограничения

1. Как и для instrument specs, `fetched_at` — observation timestamp, не точная дата вступления изменения risk tier в силу.
2. Runtime loader допускает snapshots без `page_observations`; `tier_count == len(rows)` подтверждает только внутреннее соответствие файла, не полноту API pagination. Production collector формирует page observations, но старые/ручные snapshots требуют отдельного attestation.
3. Точность position-level IM/MM зависит от исторической полноты и соответствия ladder на момент позиции; текущие snapshots не заменяют dated history.
4. Это **не** account-wide cross-margin/UTA solvency model: нет полного account collateral, offsets, portfolio margin, insurance/ADL или exchange liquidation engine. Maintenance margin result не следует называть точной liquidation price.
5. Нельзя считать один instrument snapshot и один risk snapshot синхронным состоянием без проверки их временного skew и покрытия. Наличие joint audit helper не создаёт отсутствующие исторические данные.

**Решение:** tier arithmetic/ladder checks — статически согласованы; PIT completeness и account-level liquidation — BLOCKED.

## 3. Funding arithmetic и settlement evidence

Проверено:
- `funding_accounting.py`
- `funding_archive_manifest.py`
- `scripts/validate_funding_coverage.py`
- `tests/test_funding_accounting.py`
- `tests/test_funding_archive_manifest.py`
- `tests/test_funding_coverage.py`
- `docs/audits/FUNDING_ARCHIVE_COMPLETENESS_AUDIT_2026-11-03.md`

### Арифметические инварианты

Для линейной USDT позиции знак cashflow формируется как direction sign × contract quantity × mark × funding rate:
- long платит при положительной ставке и получает при отрицательной;
- short — наоборот.
- exact contract quantity предпочтительнее реконструкции quantity из entry notional / entry price.
- duplicate settlement timestamps, missing exact mark proxy и invalid rate/mark fail closed.
- Partial TP1 allocation различает full trade-lifecycle funding и share, остающуюся в открытой части позиции. После TP1 remaining-margin helper распределяет накопленные cashflows по точному remaining contract ratio, включая settlements до TP1.
- Entry/funding и TP1/funding совпадающие границы обрабатываются консервативно; same-boundary receipts могут быть отложены, чтобы не маскировать adverse risk mark.
- Final-close boundary не зачисляет потенциальную receipt после возможного закрытия позиции.

Тесты покрывают long/short sign, partial close, exact quantity, missing mark, duplicate timestamp, entry/TP1/exit boundaries и deferred receipts.

### Внешний trust boundary

- В движке settlement mark для исторического funding берётся как Mark candle open на exact funding timestamp — это **proxy**, не доказанная точная Bybit settlement mark.
- Schedule sidecar строит UTC grid из dated instruments-info snapshots и проверяет хеши snapshot bytes, но snapshot fetched_at не доказывает effective boundary изменения fundingInterval.
- При наблюдаемом изменении интервала код fail-closed; однако snapshot observations не могут исключить смену и возврат между двумя наблюдениями.
- Funding archive validator стал существенно сильнее: hash/row count, query-page coverage, saturated-page handling, independent UTC-grid reconstruction и duplicate timestamp rejection. Но эти проверки зависят от полноты и временной достоверности schedule evidence.
- Наличие Mark свечи на timestamp не доказывает, что Funding CSV содержит все settlement events; именно поэтому прежний простой coverage validator не является самостоятельным доказательством completeness.

**Решение:** cashflow arithmetic — deterministic-testable; settlement Mark precision и complete historical schedule — BLOCKED.

## 4. Portfolio accounting

Предыдущий `PORTFOLIO_ACCOUNTING_NET_R_MAE_MFE_AUDIT_2026-11-03.md` и последующие записи фиксируют:
- closed PnL decomposition gross − fees − slippage − funding;
- partial TP1 lifecycle и per-leg fee/slippage;
- realized + unrealized equity;
- same-bar/multi-symbol order invariance и shared-capital risk budget;
- conservative taker MTM exit cost vs maker-proxy final TP, включая threshold regressions;
- UTC daily baseline ordering, price journal precision, funding allocation after TP1 и corrected execution-notional fee basis.

Это подтверждает внутренние accounting invariants в тестируемой модели. Это не снимает ограничений OHLC intrabar path, optimistic limit touch, funding mark proxy, отсутствующих Bybit archives и неполного account-level margin/liquidation.

## 5. Статус доказательств

| Контур | Code/fixture contract | Historical source completeness | Решение |
|---|---|---|---|
| Instrument specs | Strong static validation | No complete effective-time PIT archive | BLOCKED |
| Risk tiers | Strong ladder and position-level formula checks | No complete effective-time PIT archive | BLOCKED |
| Funding cashflow | Arithmetic regressions present | Settlement mark/schedule not fully authoritative | BLOCKED |
| Portfolio accounting | Several deterministic CI-backed invariants | OHLC/market/account-level realism incomplete | BLOCKED |
| Strategy PnL | Existing negative/provisional proxy evidence | No accepted Bybit-native dataset | BLOCKED |

Не заявлять, что текущий code review заменяет CI. В этом аудите тесты не запускались; все утверждения о тестовом покрытии основаны на статическом чтении исходников, тестов и ранее зафиксированных CI run records.

## 6. Разрешённые следующие шаги

- read-only аудит вызывающих участков, которые связывают instrument history, risk-tier history и portfolio engine; проверить, что они fail closed при отсутствующих snapshots, stale snapshots и несогласованном временном skew;
- при обнаружении конкретного воспроизводимого дефекта — добавить только synthetic fixture regression и прогнать deterministic research CI;
- обновлять acceptance/readiness документы, не повышая статусы без реальных источников и доказательств.

Не запускать Bybit API, collectors, архивы, PnL replay, paper/live, parameter sweeps или self-hosted runner. Не менять `main`, не сливать PR #4/#13.
