"""Tests for audited dynamic-universe CryptoFetch H1 loader."""
from pathlib import Path
import csv
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.cryptofetch_sparse_loader import load_cryptofetch_h1_sparse


def _csv_rows(symbol, start, count, close=100.0):
    import io
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=[
        "open_time_ms", "open", "high", "low", "close", "volume",
    ])
    writer.writeheader()
    for index in range(count):
        price = close + index * 0.01
        writer.writerow({
            "open_time_ms": start + index * 3_600_000,
            "open": price, "high": price + 1, "low": price - 1,
            "close": price, "volume": 100,
        })
    return stream.getvalue()


def _write_zip(path, members):
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def test_loader_keeps_late_starting_symbols_when_they_reach_common_end():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        start = 1_800_000_000_000
        members = {}
        for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]:
            offset = 0 if symbol == "BTCUSDT" else 10
            count = 100 - offset
            members[f"{symbol}_1h_fixture.csv"] = _csv_rows(
                symbol, start + offset * 3_600_000, count,
            )
        _write_zip(root / "data.zip", members)
        data, manifest, summary = load_cryptofetch_h1_sparse(root)
        assert len(data) == 5
        assert summary["included_h1_symbols"] == 5
        assert data["BTCUSDT"][0].ts == start
        assert data["ETHUSDT"][0].ts == start + 10 * 3_600_000
        assert all(rows[-1].ts == start + 99 * 3_600_000 for rows in data.values())
        assert all(row["included"] for row in manifest)


def test_loader_excludes_symbol_starting_after_common_terminal_timestamp():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        start = 1_800_000_000_000
        members = {}
        for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]:
            members[f"{symbol}_1h_fixture.csv"] = _csv_rows(
                symbol, start, 100,
            )
        members["LATEUSDT_1h_fixture.csv"] = _csv_rows(
            "LATEUSDT", start + 101 * 3_600_000, 100,
        )
        _write_zip(root / "data.zip", members)
        data, manifest, summary = load_cryptofetch_h1_sparse(root)
        assert "LATEUSDT" not in data
        late = next(row for row in manifest if row["symbol"] == "LATEUSDT")
        assert late["included"] is False
        assert late["exclusion_reason"] == "starts_after_common_terminal_timestamp"
        assert summary["included_h1_symbols"] == 5


def test_loader_fails_closed_on_conflicting_duplicate_archive_candles():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        start = 1_800_000_000_000
        common = {
            f"{symbol}_1h_fixture.csv": _csv_rows(symbol, start, 100)
            for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
        }
        _write_zip(root / "a.zip", common)
        conflicting = dict(common)
        conflicting["BTCUSDT_1h_duplicate.csv"] = _csv_rows("BTCUSDT", start, 100, close=101.0)
        _write_zip(root / "b.zip", conflicting)
        try:
            load_cryptofetch_h1_sparse(root)
        except ValueError as exc:
            assert "Conflicting duplicate OHLCV" in str(exc)
        else:
            raise AssertionError("conflicting duplicate candles must fail closed")


if __name__ == "__main__":
    tests = [(name, value) for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for name, test in tests:
        test()
        print("PASS", name)
    print(f"{len(tests)}/{len(tests)} tests passed")
