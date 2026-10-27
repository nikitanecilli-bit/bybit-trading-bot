import csv
import tempfile
import unittest
from pathlib import Path

from scripts.adapt_bybit_klines import adapt, read_klines


def write_raw(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "datetime", "open", "high", "low", "close", "volume", "turnover"])
        for ts, close in rows:
            writer.writerow([ts, "2024-01-01 00:00:00", close, close + 1, close - 1, close, 100, 1000])


class AdapterTests(unittest.TestCase):
    def test_converts_and_aligns_symbols(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw, out = root / "raw", root / "out"
            write_raw(raw / "BTCUSDT_linear_kline_15.csv", [(900000, 10), (1800000, 11), (2700000, 12)])
            write_raw(raw / "ETHUSDT_linear_kline_15.csv", [(1800000, 20), (2700000, 21), (3600000, 22)])
            count = adapt(["BTCUSDT", "ETHUSDT"], "linear", "15", raw, out)
            self.assertEqual(count, 2)
            for symbol in ("BTCUSDT", "ETHUSDT"):
                with (out / f"{symbol}.csv").open(newline="") as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual([int(r["ts"]) for r in rows], [1800000, 2700000])
                self.assertEqual(set(rows[0]), {"ts", "open", "high", "low", "close", "volume"})

    def test_rejects_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "BTCUSDT_linear_kline_15.csv"
            write_raw(path, [(900000, 10), (2700000, 12)])
            with self.assertRaisesRegex(ValueError, "missing/irregular"):
                read_klines(path, 900000)

    def test_rejects_duplicate_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "BTCUSDT_linear_kline_15.csv"
            write_raw(path, [(900000, 10), (900000, 11)])
            with self.assertRaisesRegex(ValueError, "duplicate timestamp"):
                read_klines(path, 900000)


if __name__ == "__main__":
    unittest.main()
