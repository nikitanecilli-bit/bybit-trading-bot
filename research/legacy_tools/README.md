# Legacy research tools

Файлы в этой папке — исторические standalone-прототипы, не часть активного H1 research engine и не входят в рабочий CI без отдельной проверки.

## `fast_invariant_validator_v16_legacy.py`

Архивная копия прежнего validator/digest prototype. В текущем репозитории отсутствуют импортируемые им модули:

- `Bybit_Trading_Engine_v14_Audit_Fixed`
- `quant_math_lab_v16`
- `quant_pattern_miner_v16`

Файл не является запускаемым validator и не должен использоваться как проверка торговой логики.

## Загруженные v16-прототипы (2026-11-01)

### `Institutional Quant Math Core (Part 1).py`

Набор pure-function кандидатов: FFD, Kalman velocity, KER, candle-shock intensity, path area, friction budget и pullback toxicity. Это исследовательские заготовки, а не проверенные индикаторы. Отдельные функции требуют warm-up/invalid-input tests, prefix-invariance, калибровки и проверки смысла признаков.

Особые caveats:
- `hawkes_cascade_intensity` — эвристический EWMA candle-shock score, не полноценная оценённая Hawkes-модель.
- Знак `levy_area_2d` не доказывает накопление OI до движения цены или причинность.
- `check_friction_budget_crr` использует упрощённые фиксированные тарифы и maker+maker для maker-сценария; не годится как реальная Bybit cost gate.
- KER при недостаточной истории возвращает 0.5 вместо явного warm-up/invalid результата.

### `Quant Pattern Miner & Survival Optimizer (Part 2).py`

Архивный прототип DSR, MAE/MFE heuristics и subgroup mining. Не использовать для подтверждения edge, автоисключения символов или изменения стопов:
- DSR использует per-trade Sharpe и заданное число trials, а не полный experiment ledger.
- MAE/MFE-функция не является Kaplan–Meier и не моделирует порядок событий; это не sequential counterfactual PnL.
- Риск следует брать из канонического `TradeRecord.risk_usdt`, а не восстанавливать через `pnl / r_multiple`.
- Subgroup mining зависит от порядка записей, использует малые сегменты и не корректирует множественные сравнения/FDR.

### `Institutional V16 Bridge & Enriched Runner.py`

<badge>BLOCKED — DO NOT RUN</badge>

Неисполняемый и логически небезопасный prototype:
- синтаксическая ошибка: `classQuantV16SignalGate:` без ключевого слова `class`;
- imports старого/отсутствующего engine и отсутствующих модулей;
- monkey-patch `evaluate_signal` вызывает сам себя через `evaluate_v16` (рекурсия);
- toxicity gate получает `curr.volume * 0.65` как avg volume, поэтому относительный объём теряется;
- CRR ошибочно трактует maker entry как maker+maker round trip;
- при отсутствии data-dir запускает synthetic candles.

Не исправлять косметически и не подключать к текущему движку. При необходимости создать новый adapter с dependency injection и regression tests.

## Политика

- Сохранять исходники для provenance.
- Не импортировать эти модули из production/research engine.
- Не переносить пороги (KER 0.22, Hawkes 2.8, CRR 6%, toxicity 1.35) в конфигурацию без preregistered теста.
- Все новые версии сначала помещать в отдельный модуль/ветку и проверять на synthetic invariants; рыночные выводы — только на официальных данных и независимых folds.

Полный разбор: [Quant Lab assets and hypothesis queue](../../docs/research/QUANT_LAB_ASSETS_AND_HYPOTHESIS_QUEUE_2026-11-03_RU.md).
