import json
import tempfile
import unittest
from pathlib import Path


class ReportSchemaTests(unittest.TestCase):
    def test_summary_export_preserves_negative_and_positive_symbols(self):
        # Guard the report's intended all-symbol behavior: no filtering by profitability.
        rows = [
            {"symbol": "BTCUSDT", "net_pnl": 12.5, "total_trades": 9},
            {"symbol": "DOGEUSDT", "net_pnl": -8.25, "total_trades": 11},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.json"
            path.write_text(json.dumps(rows), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual({r["symbol"] for r in loaded}, {"BTCUSDT", "DOGEUSDT"})
            self.assertTrue(any(r["net_pnl"] < 0 for r in loaded))
            self.assertTrue(any(r["net_pnl"] > 0 for r in loaded))


if __name__ == "__main__":
    unittest.main()
