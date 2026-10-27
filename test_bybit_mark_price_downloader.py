"""Offline tests for the Bybit historical mark-price downloader."""
import bybit_mark_price_downloader as dl


def test_fetch_sorts_and_deduplicates(monkeypatch):
    pages = [
        [["120000", "12", "13", "11", "12.5"]],
        [["60000", "10", "12", "9", "11"], ["60000", "10", "12", "9", "11"]],
    ]
    def fake_request(symbol, start, end, limit=dl.MAX_LIMIT, timeout=20.0):
        return pages.pop(0)
    monkeypatch.setattr(dl, "_request_page", fake_request)
    rows = dl.fetch_mark_price_klines("BTCUSDT", 60000, 120000, pause_seconds=0)
    assert [r["timestamp_ms"] for r in rows] == [60000, 120000]
    assert rows[0]["open"] == 10.0


def test_invalid_symbol_and_range():
    for args in [("BTC", 1, 2), ("BTCUSDT", 0, 2), ("BTCUSDT", 3, 2)]:
        try:
            dl.fetch_mark_price_klines(*args, pause_seconds=0)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected ValueError for {args!r}")


def test_invalid_ohlc_rejected(monkeypatch):
    monkeypatch.setattr(dl, "_request_page", lambda *a, **k: [
        ["60000", "10", "9", "8", "10"]
    ])
    try:
        dl.fetch_mark_price_klines("BTCUSDT", 60000, 60000, pause_seconds=0)
    except ValueError as exc:
        assert "OHLC boundaries" in str(exc)
    else:
        raise AssertionError("Invalid OHLC must be rejected")


def test_non_finite_prices_rejected(monkeypatch):
    monkeypatch.setattr(dl, "_request_page", lambda *a, **k: [
        ["60000", "nan", "11", "9", "10"]
    ])
    try:
        dl.fetch_mark_price_klines("BTCUSDT", 60000, 60000, pause_seconds=0)
    except ValueError:
        pass
    else:
        raise AssertionError("Non-finite prices must be rejected")
