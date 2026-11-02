# ENG-SEC-001 — harden private Bybit API credential preflight

Статус: ACCEPT — code and mocked security regression tests passed; no real credential/API request was made.  
Дата: 2026-11-02.  
Тип: authenticated read-only credential preflight.

## Подтверждённые дефекты

В `scripts/bybit_private_api_check.py` до исправления:
- принимался произвольный HTTPS base URL;
- стандартный `urllib.request.urlopen` мог следовать HTTP redirect с заголовками API key/signature;
- `retCode=False` проходил сравнение `!= 0` как будто это integer zero;
- `readOnly=True` проходил сравнение `!= 1` как будто это integer one.

## Исправления

- Strict allowlist: только `api.bybit.kz`, `api.bybit.com`, `api.bytick.com`; HTTPS, без userinfo, нестандартного порта, path, query или fragment.
- Redirects disabled with a dedicated `HTTPRedirectHandler`.
- `retCode` must be an actual integer zero; booleans and other types are rejected.
- `readOnly` must be an actual integer one; boolean `True` is rejected.
- Malformed response roots fail closed.
- Error output does not include response body, API key, secret or signature.
- Workflow remains manual-only and has `contents: read`; checkout uses `persist-credentials: false`.

## Regression tests and CI

`tests/test_bybit_private_api_check.py`: 10 tests cover deterministic V5 signature, headers, valid read-only response, writable key rejection, boolean retCode/readOnly rejection, wrong host, HTTP scheme/userinfo, redirect refusal and non-zero API response.

Full Research checks: [Actions #41469608200](https://github.com/nikitanecilli-bit/bybit-trading-bot/actions/runs/41469608200), SUCCESS. Secret scan and all configured deterministic suites passed.

## Дополнительный read-only code scan

Проверены `Bybit_Trading_Engine_v14_research.py` на ветках `Audit`, `main`, `research/bybit-funding-data-v1`, `research/data-adapter-v1`, `research/market-regime-v1-main`, `research/market-regime-v1`, `research/v15-donchian-signal`: в этих семи engine-файлах не найдено `/v5/order/create|amend|cancel`, `place_order`, `create_order` или `set_trading_stop`. Аналогичные сигнатуры не найдены в `bybit_downloader.py` и funding/mark-price downloaders там, где они существуют. Это ограниченная проверка выбранных файлов, не доказательство отсутствия mutating endpoint во всех файлах и всех исторических коммитах.

## Ограничения

- No real API key was used and no Bybit request was made.
- This validates the local preflight implementation only; it does not prove that a configured key is read-only until the user manually runs the workflow with a key that Bybit itself reports as read-only.
- No trading, wallet, transfer or withdrawal endpoint is present in this check.
