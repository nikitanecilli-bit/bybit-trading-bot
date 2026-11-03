# Legacy research tools

Файлы в этой папке — исторические standalone-прототипы, не часть активного H1 research engine и не входят в рабочий CI без отдельной проверки.

## fast_invariant_validator_v16_legacy.py

Архивная копия прежнего validator/digest prototype. В текущем репозитории отсутствуют импортируемые им модули:

- `Bybit_Trading_Engine_v14_Audit_Fixed`
- `quant_math_lab_v16`
- `quant_pattern_miner_v16`

Поэтому файл не является запускаемым validator и не должен использоваться как проверка торговой логики. Перемещение не меняло его исходный код. Для возвращения в активную разработку сначала восстановить/заменить зависимости, написать tests и проверить accounting semantics на текущем TradeRecord schema.
