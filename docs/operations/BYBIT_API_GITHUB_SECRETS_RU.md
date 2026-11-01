# Безопасное подключение Bybit API через GitHub Secrets

Статус: подготовлена инфраструктура; проверка реальной авторизации ожидает добавления новых секретов владельцем репозитория.

## Что добавлено

- `.github/workflows/bybit-private-api-check.yml` — ручной workflow, который запускает только проверку авторизации.
- `scripts/bybit_private_api_check.py` — HMAC-SHA256 подпись Bybit V5 и проверка endpoint `GET /v5/user/query-api`.
- `tests/test_bybit_private_api_check.py` — локальные unit-тесты подписи и проверок read-only.

Workflow не использует торговые, transfer или withdrawal endpoint. Он не сохраняет секреты в артефакты, не печатает API key/secret/signature и не коммитит полученный ответ. Права GitHub Actions ограничены `contents: read`, checkout не сохраняет Git credentials.

## 1. Отозвать ранее раскрытый ключ

Ключ, ранее отправленный в чат, следует считать скомпрометированным. Отзови его в Bybit API Management и создай отдельный новый ключ. Не используй повторно раскрытый ключ.

## 2. Создать новый ключ Bybit

В веб-версии Bybit открой API Management:
https://www.bybit.com/app/user/api-management

Для аккаунта Казахстана API V5 обычно использует региональный REST host `https://api.bybit.kz`; если настройки аккаунта указывают другой host, выбери соответствующий ему endpoint.

Настройки ключа:
- System-generated HMAC key (API Key + API Secret).
- Read-Only включён.
- Не включать Contract Trade, Spot Trade, Derivatives Trade, Wallet Transfer, Withdraw или другие права записи.
- Если Bybit позволяет IP restriction, включай его только при наличии стабильного исходящего IP. GitHub-hosted runners используют меняющиеся адреса; не добавляй случайный IP. Для обязательного IP allowlist потребуется self-hosted runner со статическим IP.

API Secret показывается при создании ключа; сохрани его сразу в менеджере паролей и GitHub Secret. Не отправляй его в чат, issue, commit или workflow input.

## 3. Добавить GitHub Secrets

В репозитории открой:
Settings → Secrets and variables → Actions → New repository secret

Создай два Repository secrets с точными именами:
- `BYBIT_API_KEY`
- `BYBIT_API_SECRET`

Вставь значения в соответствующие поля и сохрани. Не добавляй их в Variables, обычные файлы, `.env` в Git или YAML workflow.

## 4. Запустить проверку

Открой:
Actions → Bybit private API credential check (read-only) → Run workflow

Выбери `https://api.bybit.kz` для аккаунта Казахстана, если Bybit не указал иной региональный endpoint. Запусти workflow вручную.

Ожидаемый успешный результат:
- авторизация подтверждена;
- API key отмечен как read-only;
- workflow сообщает, что торговые/переводные/withdrawal запросы не выполнялись.

## 5. Как интерпретировать ошибку

- HTTP 403: сетевой/региональный/IP отказ. Это не доказательство неправильной подписи. Проверь региональный host и ограничения IP. Если GitHub-hosted runner блокируется, используй self-hosted runner со стабильным IP или локальный сборщик.
- retCode 10003: неверный API key либо ключ не подходит для выбранного окружения/домена.
- retCode 10004: подпись не прошла проверку; проверь соответствие API Secret и тип ключа HMAC.
- retCode 10005: недостаточные разрешения для endpoint; endpoint `/v5/user/query-api` согласно документации доступен с любыми правами.
- Missing secrets: оба repository secrets ещё не добавлены или имеют другие имена.

Workflow намеренно не выводит тело HTTP-ошибки и полный ответ Bybit, чтобы не раскрыть данные аккаунта.

## 6. После успешной проверки

Это подтверждает только безопасную приватную авторизацию. Следующий отдельный этап — сбор публичных market data и датированных instrument specs с Bybit, затем сверка данных и execution sizing. Наличие API-ключа не исправляет сетевой HTTP 403 автоматически.

Документация Bybit:
- https://bybit-exchange.github.io/docs/v5/user/apikey-info
- https://bybit-exchange.github.io/docs/v5/guide
