#!/usr/bin/env python3
"""
Загрузчик рыночных данных Bybit (v5) для бэктестов.

Наборы данных (--datasets):
  kline    свечи last price (OHLCV + turnover)
  mark     свечи mark price   - по ним считается ликвидация и PnL на бирже
  index    свечи index price
  premium  свечи premium index (basis)
  funding  история funding rate (ставка и время расчёта)
  oi       история open interest
  instrument  спецификация контракта: tick size, шаг лота, мин. объём/ноционал, плечи
  all      всё перечисленное
По умолчанию: kline mark funding oi instrument.

Возможности:
- вся история за период (пагинация), несколько символов и таймфреймов;
- докачка: повторный запуск продолжает с последней сохранённой записи;
- незакрытая свеча отбрасывается;
- повторы при rate limit / сетевых ошибках;
- проверка пропусков в готовых файлах;
- API-ключи не нужны: всё это публичные данные.

Примеры:
    python bybit_downloader.py --symbols SOLUSDT --intervals 15 --start 2023-01-01
    python bybit_downloader.py --symbols BTCUSDT SOLUSDT --intervals 15 60 --datasets all --out data

Файлы в --out:
    <SYM>_<cat>_kline_<int>.csv   <SYM>_<cat>_mark_<int>.csv   <SYM>_<cat>_funding.csv
    <SYM>_<cat>_oi_<oiint>.csv    <SYM>_<cat>_instrument.json
Время везде: timestamp (мс, UTC) + datetime (UTC). У свечей это время ОТКРЫТИЯ.
Зависимости: pip install requests
"""
import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

DEFAULT_BASE_URL = "https://api.bybit.com"  # при блокировке: https://api.bybit.kz / .nl / .ae (см. --base-url)

MIN_MS = 60_000
DAY_MS = 86_400_000
# Длительность свечи, мс. Для W и M значения приблизительные (нужны лишь для
# отсечения незакрытой свечи); проверка пропусков для них отключена.
INTERVAL_MS = {
    "1": MIN_MS, "3": 3 * MIN_MS, "5": 5 * MIN_MS, "15": 15 * MIN_MS,
    "30": 30 * MIN_MS, "60": 60 * MIN_MS, "120": 120 * MIN_MS,
    "240": 240 * MIN_MS, "360": 360 * MIN_MS, "720": 720 * MIN_MS,
    "D": DAY_MS, "W": 7 * DAY_MS, "M": 28 * DAY_MS,
}
GAP_CHECK_INTERVALS = set(INTERVAL_MS) - {"W", "M"}
OI_INTERVAL_MS = {"5min": 5 * MIN_MS, "15min": 15 * MIN_MS, "30min": 30 * MIN_MS,
                  "1h": 60 * MIN_MS, "4h": 240 * MIN_MS, "1d": DAY_MS}

KLINE_COLS = ["open", "high", "low", "close", "volume", "turnover"]
PRICE_COLS = ["open", "high", "low", "close"]


def _kline6(it):
    return int(it[0]), it[1:7]


def _kline4(it):
    return int(it[0]), it[1:5]


def _funding(it):
    return int(it["fundingRateTimestamp"]), [it["fundingRate"]]


def _oi(it):
    return int(it["timestamp"]), [it["openInterest"]]


# kind: kline = привязан к таймфрейму свечей; oi = к --oi-interval; funding = без интервала
SPECS = {
    "kline":   dict(path="/v5/market/kline", keys=("start", "end"), limit=1000,
                    columns=KLINE_COLS, parse=_kline6, kind="kline"),
    "mark":    dict(path="/v5/market/mark-price-kline", keys=("start", "end"), limit=1000,
                    columns=PRICE_COLS, parse=_kline4, kind="kline"),
    "index":   dict(path="/v5/market/index-price-kline", keys=("start", "end"), limit=1000,
                    columns=PRICE_COLS, parse=_kline4, kind="kline"),
    "premium": dict(path="/v5/market/premium-index-price-kline", keys=("start", "end"), limit=1000,
                    columns=PRICE_COLS, parse=_kline4, kind="kline"),
    "funding": dict(path="/v5/market/funding/history", keys=("startTime", "endTime"), limit=200,
                    columns=["funding_rate"], parse=_funding, kind="funding"),
    "oi":      dict(path="/v5/market/open-interest", keys=("startTime", "endTime"), limit=200,
                    columns=["open_interest"], parse=_oi, kind="oi", cursor=True),
}
DEFAULT_DATASETS = ["kline", "mark", "funding", "oi", "instrument"]
ALL_DATASETS = ["kline", "mark", "index", "premium", "funding", "oi", "instrument"]

log = logging.getLogger("bybit_downloader")


def now_ms() -> int:
    return int(time.time() * 1000)


def ms_to_str(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def parse_date(value: str) -> int:
    if value.lower() == "now":
        return now_ms()
    dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def api_get(session, base_url, path, params, retries=6):
    """GET к публичному API Bybit с повторами. Возвращает data['result']."""
    for attempt in range(1, retries + 1):
        wait = min(2 ** attempt, 60)
        try:
            resp = session.get(base_url + path, params=params, timeout=15)
            if resp.status_code == 403:
                raise RuntimeError(
                    "HTTP 403: Bybit закрыл доступ (регион/IP или временный бан за превышение "
                    "лимита). Смените сеть/VPN, попробуйте --base-url с региональным доменом "
                    "или подождите ~10 минут."
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                log.warning("HTTP %s, повтор через %ss (%s/%s)", resp.status_code, wait, attempt, retries)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            code = data.get("retCode")
            if code == 0:
                return data["result"]
            if code in (10006, 10016):  # rate limit / сервер занят
                log.warning("retCode %s, повтор через %ss", code, wait)
                time.sleep(wait)
                continue
            raise RuntimeError(f"Bybit error {code}: {data.get('retMsg')} ({path} {params.get('symbol')})")
        except (requests.ConnectionError, requests.Timeout) as exc:
            log.warning("Сетевая ошибка: %s; повтор через %ss (%s/%s)", exc, wait, attempt, retries)
            time.sleep(wait)
    raise RuntimeError(f"Не удалось получить {path} после {retries} попыток")


def read_timestamps(path: Path):
    if not path.exists():
        return []
    with path.open(newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        return [int(row[0]) for row in reader if row]


def find_gaps(timestamps, step_ms):
    """Пропуски: (первая_отсутствующая_свеча, последняя_отсутствующая, кол-во)."""
    gaps = []
    for prev, cur in zip(timestamps, timestamps[1:]):
        if cur - prev > step_ms:
            gaps.append((prev + step_ms, cur - step_ms, (cur - prev) // step_ms - 1))
    return gaps


def collect(session, base_url, spec, base_params, start_ms, end_ms, delay):
    """Листает историю от новых записей к старым и возвращает {ts: [значения]}."""
    start_key, end_key = spec["keys"]
    rows, cursor_end, api_cursor = {}, end_ms, None
    while cursor_end >= start_ms:
        params = dict(base_params, **{start_key: start_ms, end_key: cursor_end, "limit": spec["limit"]})
        if api_cursor:
            params["cursor"] = api_cursor
        result = api_get(session, base_url, spec["path"], params)
        items = result.get("list") or []
        if not items:
            break
        parsed = [spec["parse"](it) for it in items]
        for ts, vals in parsed:
            rows[ts] = vals
        oldest = min(ts for ts, _ in parsed)
        log.info("  ... до %s (всего %s)", ms_to_str(oldest), len(rows))
        if oldest <= start_ms:
            break
        next_cursor = result.get("nextPageCursor") if spec.get("cursor") else None
        if next_cursor:
            api_cursor = next_cursor        # курсорная пагинация (open interest)
        else:
            api_cursor = None
            cursor_end = oldest - 1         # пагинация по времени
        time.sleep(delay)
    return rows


def download_dataset(session, base_url, name, category, symbol, interval, oi_interval,
                     start_ms, end_ms, out_dir: Path, delay=0.12):
    spec = SPECS[name]
    kind = spec["kind"]
    params = {"category": category, "symbol": symbol}
    if kind == "kline":
        params["interval"] = interval
        step, suffix = INTERVAL_MS[interval], f"_{interval}"
    elif kind == "oi":
        params["intervalTime"] = oi_interval
        step, suffix = OI_INTERVAL_MS[oi_interval], f"_{oi_interval}"
    else:
        step, suffix = None, ""

    path = out_dir / f"{symbol}_{category}_{name}{suffix}.csv"
    tag = f"{symbol} {name}{suffix}"

    existing = read_timestamps(path)
    if existing:
        start_ms = max(start_ms, existing[-1] + (step or 1))
        log.info("%s: файл есть (%s записей), докачка с %s", tag, len(existing), ms_to_str(start_ms))
    if start_ms > end_ms:
        log.info("%s: нечего докачивать", tag)
        return path

    rows = collect(session, base_url, spec, params, start_ms, end_ms, delay)

    cutoff = now_ms()
    keep = [ts for ts in sorted(rows)
            if start_ms <= ts <= end_ms and (kind != "kline" or ts + step <= cutoff)]  # только закрытые свечи
    if not keep:
        log.info("%s: новых данных нет", tag)
        return path

    out_dir.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["timestamp", "datetime"] + spec["columns"])
        for ts in keep:
            w.writerow([ts, ms_to_str(ts)] + list(rows[ts]))
    log.info("%s: записано %s -> %s", tag, len(keep), path.name)

    if step and (kind == "oi" or interval in GAP_CHECK_INTERVALS):
        gaps = find_gaps(read_timestamps(path), step)
        if gaps:
            log.warning("%s: пропусков %s (не хватает %s), первые: %s", tag, len(gaps),
                        sum(g[2] for g in gaps), [(ms_to_str(a), n) for a, _, n in gaps[:3]])
        else:
            log.info("%s: пропусков нет", tag)
    return path


def download_instrument(session, base_url, category, symbol, out_dir: Path):
    """Текущая спецификация контракта (tick size, шаг лота, мин. ноционал, плечи, интервал funding)."""
    result = api_get(session, base_url, "/v5/market/instruments-info",
                     {"category": category, "symbol": symbol})
    items = result.get("list") or []
    if not items:
        raise RuntimeError(f"instruments-info: символ {symbol} ({category}) не найден")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{symbol}_{category}_instrument.json"
    path.write_text(json.dumps({"fetched_at": ms_to_str(now_ms()), "instrument": items[0]},
                               ensure_ascii=False, indent=2))
    log.info("%s instrument: сохранено -> %s", symbol, path.name)
    return path


def main(argv=None):
    p = argparse.ArgumentParser(description="Загрузка рыночных данных Bybit для бэктестов")
    p.add_argument("--symbols", nargs="+", default=["SOLUSDT"])
    p.add_argument("--intervals", nargs="+", default=["15"], help="1 3 5 15 30 60 120 240 360 720 D W M")
    p.add_argument("--datasets", nargs="+", default=DEFAULT_DATASETS,
                   choices=ALL_DATASETS + ["all"], help="по умолчанию: " + " ".join(DEFAULT_DATASETS))
    p.add_argument("--oi-interval", default="15min", choices=list(OI_INTERVAL_MS))
    p.add_argument("--category", default="linear", choices=["linear", "inverse", "spot"],
                   help="linear = USDT-перпетуалы (по умолчанию)")
    p.add_argument("--start", default="2023-01-01", help="YYYY-MM-DD (UTC)")
    p.add_argument("--end", default="now", help="YYYY-MM-DD (UTC) или now")
    p.add_argument("--out", default="data")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--delay", type=float, default=0.12, help="пауза между запросами, сек")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")

    bad = [i for i in args.intervals if i not in INTERVAL_MS]
    if bad:
        p.error(f"Неизвестные интервалы: {bad}")
    datasets = ALL_DATASETS if "all" in args.datasets else args.datasets
    if args.category == "spot":
        skipped = [d for d in datasets if d not in ("kline", "instrument")]
        if skipped:
            log.warning("Для spot недоступны: %s - пропускаю", ", ".join(skipped))
        datasets = [d for d in datasets if d in ("kline", "instrument")]

    start_ms, end_ms = parse_date(args.start), parse_date(args.end)
    if start_ms >= end_ms:
        p.error("--start должен быть раньше --end")

    out_dir, base = Path(args.out), args.base_url.rstrip("/")
    session = requests.Session()
    try:
        for symbol in (s.upper() for s in args.symbols):
            if "instrument" in datasets:
                download_instrument(session, base, args.category, symbol, out_dir)
            for name in ("funding", "oi"):  # не зависят от таймфрейма свечей
                if name in datasets:
                    download_dataset(session, base, name, args.category, symbol, None,
                                     args.oi_interval, start_ms, end_ms, out_dir, args.delay)
            for interval in args.intervals:
                for name in ("kline", "mark", "index", "premium"):
                    if name in datasets:
                        download_dataset(session, base, name, args.category, symbol, interval,
                                         args.oi_interval, start_ms, end_ms, out_dir, args.delay)
    except KeyboardInterrupt:
        log.info("Остановлено пользователем. Скачанное сохранено, при перезапуске докачается.")
        return 130
    except RuntimeError as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())