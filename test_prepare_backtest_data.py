import csv
import tempfile
import unittest
from pathlib import Path

from prepare_backtest_data import convert_file


class PrepareBacktestDataTests(unittest.TestCase):
    def _write_input(self, path, rows):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["timestamp", "datetime", "open", "high", "low", "close", "volume", "turnover"],
            )
            writer.writeheader()
            writer.writerows(rows)

    def _row(self, ts, op="100", hi="102", lo="99", cl="101", vol="12"):
        return {
            "timestamp": str(ts),
            "datetime": "2026-01-01 00:00:00",
            "open": op,
            "high": hi,
            "low": lo,
            "close": cl,
            "volume": vol,
            "turnover": "1200",
        }

    def test_converts_and_sorts_valid_candles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output = root / "BTCUSDT_linear_kline_15.csv", root / "BTCUSDT.csv"
            self._write_input(source, [self._row(1_700_001_800_000), self._row(1_700_000_900_000)])
            result = convert_file(source, output, 900_000)
            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(list(rows[0]), ["ts", "open", "high", "low", "close", "volume"])
            self.assertEqual([int(row["ts"]) for row in rows], [1_700_000_900_000, 1_700_001_800_000])
            self.assertEqual(result["rows"], 2)

    def test_rejects_irregular_intervals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "BTCUSDT_linear_kline_15.csv"
            self._write_input(source, [self._row(900_000), self._row(2_700_000), self._row(3_000_000)])
            with self.assertRaisesRegex(ValueError, "irregular candle intervals"):
                convert_file(source, root / "BTCUSDT.csv", None)

    def test_rejects_duplicate_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "BTCUSDT_linear_kline_15.csv"
            self._write_input(source, [self._row(900_000), self._row(900_000)])
            with self.assertRaisesRegex(ValueError, "duplicate timestamps"):
                convert_file(source, root / "BTCUSDT.csv", None)

    def test_rejects_invalid_ohlc(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "BTCUSDT_linear_kline_15.csv"
            self._write_input(source, [self._row(900_000, hi="98"), self._row(1_800_000)])
            with self.assertRaisesRegex(ValueError, "invalid OHLC boundaries"):
                convert_file(source, root / "BTCUSDT.csv", None)


if __name__ == "__main__":
    unittest.main()
