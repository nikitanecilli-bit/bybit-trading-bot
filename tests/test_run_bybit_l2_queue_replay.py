from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from decimal import Decimal
from unittest.mock import patch

import scripts.run_bybit_l2_queue_replay as runner
import scripts.inspect_bybit_trade_sample as trade_inspector
import scripts.inspect_bybit_orderbook_sample as book_inspector
from scripts.run_bybit_l2_queue_replay import (
    HOUR_MS, capture_book_states_at, capture_scenarios,
)


def test_trade_sample_inspector_recognizes_both_block_trade_aliases():
    assert trade_inspector.block_trade_flag_columns(["timestamp", "BT"]) == ["BT"]
    assert trade_inspector.block_trade_flag_columns(["isBlockTrade"]) == ["isBlockTrade"]
    assert trade_inspector.block_trade_flag_columns(["BT", "isBlockTrade"]) == [
        "isBlockTrade", "BT",
    ]
    assert trade_inspector.block_trade_flag_columns(["timestamp", "RPI"]) == []


def test_trade_sample_inspector_uses_shared_exact_millisecond_timestamp_parser():
    parser = trade_inspector.parse_trade_timestamp_ms
    assert parser("1700000000.123") == 1_700_000_000_123
    assert parser("1700000000123") == 1_700_000_000_123
    for value in ("1700000000.1234", "1700000000123.5"):
        try:
            parser(value)
        except ValueError as exc:
            assert "sub-millisecond" in str(exc)
        else:
            raise AssertionError("sub-millisecond trade timestamp must fail closed")
    for value in ("NaN", "Infinity", "0", "-1", "not-a-timestamp"):
        try:
            parser(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid timestamp must be rejected: {value!r}")

def test_trade_sample_inspector_classifies_missing_malformed_and_duplicate_ids():
    seen = set()
    assert trade_inspector.classify_trade_id(None, seen) == "missing"
    assert trade_inspector.classify_trade_id("", seen) == "missing"
    assert trade_inspector.classify_trade_id("   ", seen) == "missing"
    assert trade_inspector.classify_trade_id(" trade-1 ", seen) == "malformed"
    assert trade_inspector.classify_trade_id("trade-1", seen) == "unique"
    assert trade_inspector.classify_trade_id("trade-1", seen) == "duplicate"
    assert seen == {"trade-1"}


def test_trade_sample_inspector_validates_flag_alias_values_and_conflicts():
    classify = trade_inspector.classify_boolean_flag_aliases
    assert classify({}, [], "block trade") == "missing"
    assert classify({"BT": None}, ["BT"], "block trade") == "missing"
    assert classify({"BT": ""}, ["BT"], "block trade") == "missing"
    assert classify({"BT": "not-a-flag"}, ["BT"], "block trade") == "malformed"
    assert classify({"BT": "1"}, ["BT"], "block trade") == "true"
    assert classify({"RPI": "0"}, ["RPI"], "RPI") == "false"
    assert classify(
        {"BT": "0", "isBlockTrade": "0"},
        ["BT", "isBlockTrade"], "block trade",
    ) == "false"
    assert classify(
        {"BT": "0", "isBlockTrade": "1"},
        ["BT", "isBlockTrade"], "block trade",
    ) == "conflict"


def test_trade_sample_inspector_rejects_duplicate_or_missing_header_columns():
    try:
        trade_inspector.validate_trade_csv_header(
            ["timestamp", "symbol", "side", "size", "price", "timestamp"],
        )
    except ValueError as exc:
        assert "duplicate column names" in str(exc)
    else:
        raise AssertionError("duplicate CSV header columns must be rejected")

    try:
        trade_inspector.validate_trade_csv_header(
            ["timestamp", "symbol", "side", "size"],
        )
    except ValueError as exc:
        assert "missing required columns" in str(exc)
    else:
        raise AssertionError("missing required CSV headers must be rejected")


def test_trade_sample_inspector_rejects_extra_or_missing_row_fields():
    try:
        trade_inspector.validate_trade_csv_row(
            {"timestamp": "1", "symbol": "AAVEUSDT", "side": "Buy",
             "size": "1", "price": "1", None: ["extra"]}, 2,
        )
    except ValueError as exc:
        assert "unexpected extra CSV fields" in str(exc)
    else:
        raise AssertionError("extra CSV fields must be rejected")

    try:
        trade_inspector.validate_trade_csv_row(
            {"timestamp": "1", "symbol": "AAVEUSDT", "side": "Buy",
             "size": "1", "price": None}, 3,
        )
    except ValueError as exc:
        assert "missing CSV field value" in str(exc)
    else:
        raise AssertionError("missing row values must be rejected")


def test_orderbook_inspector_uses_strict_integer_timestamp_and_sequence_fields():
    parse_fields = book_inspector.parse_event_integer_fields
    valid = {"ts": 1000, "cts": 999, "data": {"seq": 2, "u": 3}}
    assert parse_fields(valid) == (1000, 999, 2, 3)
    missing_cts = {"ts": 1000, "data": {"seq": 2, "u": 3}}
    assert parse_fields(missing_cts) == (1000, None, 2, 3)

    cases = [
        ({"ts": True, "cts": 999, "data": {"seq": 2, "u": 3}}, "ts must be an integer"),
        ({"ts": 1000.5, "cts": 999, "data": {"seq": 2, "u": 3}}, "ts must be an integer"),
        ({"ts": 1000, "cts": 999.5, "data": {"seq": 2, "u": 3}}, "cts must be an integer"),
        ({"ts": 1000, "cts": 999, "data": {"seq": "2", "u": 3}}, "seq must be an integer"),
        ({"ts": 1000, "cts": 999, "data": {"seq": 2, "u": True}}, "u must be an integer"),
        ({"ts": 0, "cts": 999, "data": {"seq": 2, "u": 3}}, "must be positive"),
    ]
    for event, expected in cases:
        try:
            parse_fields(event)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid order-book integer fields must fail: {event!r}")



def write_book_archive(path: Path, events: list[dict]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "events.data",
            "".join(json.dumps(event) + "\n" for event in events),
        )


def event(kind: str, cts: int, seq: int, update_id: int, bid_qty: str) -> dict:
    return {
        "type": kind,
        "cts": cts,
        "data": {
            "s": "AAVEUSDT",
            "seq": seq,
            "u": update_id,
            "b": [["100", bid_qty]],
            "a": [["101", "5"]],
        },
    }


def test_capture_scenarios_uses_pre_boundary_book_state():
    first = 1_000
    events = [event("snapshot", first, 1, 1, "5")]
    boundary_hours = (2, 8, 14, 20)
    for seq, hours in enumerate(boundary_hours, 2):
        events.append(event("delta", first + hours * HOUR_MS, seq, seq, str(seq + 5)))
    events.append(event("delta", first + 21 * HOUR_MS, 6, 6, "20"))

    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "book.zip"
        write_book_archive(archive, events)
        snapshots, coverage = capture_scenarios(archive)

    assert [item["arrival_ts"] for item in snapshots] == [
        first + hours * HOUR_MS for hours in boundary_hours
    ]
    assert [item["book_cts"] for item in snapshots] == [
        first,
        first + 2 * HOUR_MS,
        first + 8 * HOUR_MS,
        first + 14 * HOUR_MS,
    ]
    assert [item["bids"][100] for item in snapshots] == [
        5, 7, 8, 9,
    ]
    assert coverage["events_scanned"] == 6


def test_capture_scenarios_rejects_archive_without_all_arrival_boundaries():
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "short.zip"
        write_book_archive(archive, [
            event("snapshot", 1_000, 1, 1, "5"),
            event("delta", 1_000 + 3 * HOUR_MS, 2, 2, "6"),
        ])
        try:
            capture_scenarios(archive)
        except ValueError as exc:
            assert "does not cover all scheduled arrival times" in str(exc)
        else:
            raise AssertionError("short archive must not fabricate scheduled scenarios")


def test_markout_capture_excludes_exact_target_event_and_never_extrapolates():
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "book.zip"
        write_book_archive(archive, [
            event("snapshot", 1_000, 1, 1, "5"),
            event("delta", 2_000, 2, 2, "8"),
            event("delta", 4_000, 3, 3, "9"),
        ])
        states = capture_book_states_at(archive, [2_000, 3_500, 5_000])

    assert states[2_000]["book_cts"] == 1_000
    assert states[2_000]["bids"][100] == 5
    assert states[3_500]["book_cts"] == 2_000
    assert states[3_500]["bids"][100] == 8
    assert 5_000 not in states


def test_capture_scenarios_rejects_empty_order_book_archive():
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "empty.zip"
        write_book_archive(archive, [])
        try:
            capture_scenarios(archive)
        except ValueError as exc:
            assert "order-book archive contains no events" in str(exc)
        else:
            raise AssertionError("empty order-book archive must fail with a clear validation error")


def test_markout_capture_rejects_out_of_order_archive_after_last_target():
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "out_of_order.zip"
        write_book_archive(archive, [
            event("snapshot", 1_000, 1, 1, "5"),
            event("delta", 3_000, 3, 3, "8"),
            event("delta", 2_500, 4, 4, "9"),
        ])
        try:
            capture_book_states_at(archive, [2_000])
        except ValueError as exc:
            assert "non-monotonic matching-engine timestamp" in str(exc)
        else:
            raise AssertionError("out-of-order tail must invalidate markout archive")


def test_post_fill_markout_separates_spread_capture_from_mid_price_move():
    results = [{
        "fills": [{
            "timestamp_ms": 2_000,
            "side": "Buy",
            "price": "99",
            "quantity": "1",
        }],
    }]
    states = {
        2_000: {
            "book_cts": 1_000,
            "bids": {Decimal("99"): Decimal("5")},
            "asks": {Decimal("101"): Decimal("5")},
        },
        3_000: {
            "book_cts": 2_500,
            "bids": {Decimal("100"): Decimal("5")},
            "asks": {Decimal("102"): Decimal("5")},
        },
    }
    with patch.object(runner, "capture_book_states_at", return_value=states):
        runner.add_post_fill_markouts(Path("unused.zip"), results)

    fill = results[0]["fills"][0]
    markout = next(x for x in fill["post_fill_markout"] if x["horizon_ms"] == 1_000)
    assert fill["pre_fill_book_state"]["mid_price"] == "100"
    assert markout["signed_fill_to_future_mid_bps"] == str(Decimal("202.0202020202020202020202020"))
    assert Decimal(markout["signed_mid_move_from_pre_fill_bps"]) == Decimal("100")
    assert markout["pre_fill_mid_price"] == "100"


if __name__ == "__main__":
    test_names = sorted(
        name for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    )
    for name in test_names:
        globals()[name]()
        print(f"PASS {name}")
    print(f"{len(test_names)}/{len(test_names)} tests passed")
