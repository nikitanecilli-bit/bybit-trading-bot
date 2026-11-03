"""Tests for immutable H1 portfolio validation manifests."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_h1_shared_capital_portfolio_validation import (
    build_validation_manifest,
    write_validation_manifest,
)


def _write_kline(path, start_ts, count):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "symbol", "timestamp_ms", "open", "high", "low", "close", "volume", "turnover",
        ])
        writer.writeheader()
        for index in range(count):
            price = 100.0 + index * 0.01
            writer.writerow({
                "symbol": "BTCUSDT",
                "timestamp_ms": start_ts + index * 3_600_000,
                "open": price,
                "high": price + 1,
                "low": price - 1,
                "close": price + 0.1,
                "volume": 100,
                "turnover": 10_000,
            })


class H1ValidationManifestTests(unittest.TestCase):
    def test_manifest_hashes_exact_inputs_code_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kline_dir = root / "kline"
            funding_dir = root / "funding"
            mark_dir = root / "mark"
            specs_dir = root / "specs"
            risk_dir = root / "risk"
            for directory in (kline_dir, funding_dir, mark_dir, specs_dir, risk_dir):
                directory.mkdir()

            start_ts = 1_800_000_000_000
            kline_path = kline_dir / "BTCUSDT.csv"
            _write_kline(kline_path, start_ts, 100)
            (funding_dir / "BTCUSDT.csv").write_text(
                "funding_timestamp_ms,rate\\n1800003600000,0.0001\\n",
                encoding="utf-8",
            )
            (mark_dir / "BTCUSDT.csv").write_text(
                "timestamp_ms,open,high,low,close\\n1800003600000,100,101,99,100\\n",
                encoding="utf-8",
            )
            (specs_dir / "2026-01-01.json").write_text(
                json.dumps({"fetched_at": "2026-01-01T00:00:00Z"}), encoding="utf-8",
            )
            (risk_dir / "2026-01-01.json").write_text(
                json.dumps({"fetched_at": "2026-01-01T00:00:00Z"}), encoding="utf-8",
            )
            output_csv = root / "portfolio.csv"
            output_csv.write_text("fold,symbol_list\\n1,BTCUSDT\\n", encoding="utf-8")

            timestamps = [start_ts + index * 3_600_000 for index in range(100)]
            rows = [{"fold": 1, "symbol_list": "BTCUSDT", "net_pnl": -12.5}]
            manifest = build_validation_manifest(
                symbols=["BTCUSDT"],
                archives={"BTCUSDT": str(kline_path)},
                common_timestamps=timestamps,
                kline_dir=kline_dir,
                funding_dir=funding_dir,
                mark_price_dir=mark_dir,
                instrument_specs_dir=specs_dir,
                risk_tiers_dir=risk_dir,
                result_rows=rows,
                output_csv_path=output_csv,
            )

            source = manifest["input_files"]["trade_kline"]["selected_sources"]["BTCUSDT"]
            self.assertEqual(source["row_count"], 100)
            self.assertEqual(source["first_timestamp_ms"], start_ts)
            self.assertEqual(source["last_timestamp_ms"], timestamps[-1])
            self.assertEqual(
                source["sha256"],
                hashlib.sha256(kline_path.read_bytes()).hexdigest(),
            )
            self.assertEqual(manifest["universe"]["selected_symbols"], ["BTCUSDT"])
            self.assertEqual(manifest["common_h1_grid"]["bar_count"], 100)
            self.assertEqual(manifest["folds"][0]["start_timestamp_ms"], timestamps[50])
            self.assertEqual(manifest["folds"][0]["end_timestamp_ms"], timestamps[64])
            self.assertEqual(
                manifest["outputs"]["portfolio_results_csv"]["sha256"],
                hashlib.sha256(output_csv.read_bytes()).hexdigest(),
            )
            self.assertTrue(any(
                item["path"].endswith("Bybit_Trading_Engine_v14_research.py")
                for item in manifest["code_files"]
            ))
            self.assertEqual(manifest["result_rows"], rows)

            manifest_path = write_validation_manifest(
                manifest, root / "validation_manifest.json",
            )
            restored = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(restored, manifest)

    def test_manifest_rejects_missing_selected_source(self):
        with self.assertRaisesRegex(ValueError, "missing selected kline source"):
            build_validation_manifest(
                symbols=["BTCUSDT"],
                archives={},
                common_timestamps=[1_800_000_000_000],
                kline_dir=".",
                funding_dir=".",
                mark_price_dir=".",
                instrument_specs_dir=".",
                risk_tiers_dir=".",
                result_rows=[],
                output_csv_path=__file__,
            )

    def test_manifest_rejects_unsorted_or_duplicate_common_grid(self):
        for timestamps in (
            [1_800_003_600_000, 1_800_000_000_000],
            [1_800_000_000_000, 1_800_000_000_000],
        ):
            with self.subTest(timestamps=timestamps):
                with self.assertRaisesRegex(ValueError, "unique and sorted"):
                    build_validation_manifest(
                        symbols=["BTCUSDT"],
                        archives={"BTCUSDT": __file__},
                        common_timestamps=timestamps,
                        kline_dir=".",
                        funding_dir=".",
                        mark_price_dir=".",
                        instrument_specs_dir=".",
                        risk_tiers_dir=".",
                        result_rows=[],
                        output_csv_path=__file__,
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
