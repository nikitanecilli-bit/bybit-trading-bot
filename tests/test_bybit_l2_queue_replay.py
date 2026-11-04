from decimal import Decimal as D
import sys
import json
import zipfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scripts.run_bybit_l2_queue_replay as l2_runner
import bybit_l2_queue_replay as l2_module
from bybit_instrument_specs import InstrumentSpec
from bybit_l2_queue_replay import (
    OrderBook, apply_public_trade, capture_book_at, per_fill_fee_ledger, place_passive_order, signed_markout_bps,
)


def book():
    b = OrderBook()
    b.apply({
        "type": "snapshot", "cts": 1000,
        "data": {"seq": 1, "u": 1, "b": [["100", "5"], ["99", "8"]],
                 "a": [["101", "6"], ["102", "9"]]},
    })
    return b


def order(b=None, side="Buy", price="100", qty="2", arrival=1001, expiry=5000):
    return place_passive_order(
        b or book(), side=side, price=D(price), quantity=D(qty),
        arrival_ts=arrival, expiry_ts=expiry,
    )


def trade(ts, side, price, size, rpi="0"):
    return {
        "timestamp_ms": ts, "side": side, "price": price, "size": size,
        "rpi": rpi, "block_trade": "0",
    }




def test_passive_order_accepts_exact_exchange_instrument_constraints():
    spec = InstrumentSpec.from_snapshot({"instrument": {
        "symbol": "TESTUSDT", "category": "linear", "status": "Trading",
        "priceFilter": {"minPrice": "0.1", "maxPrice": "1000000", "tickSize": "0.1"},
        "lotSizeFilter": {"qtyStep": "0.01", "minOrderQty": "0.05",
                          "maxOrderQty": "1000", "maxMktOrderQty": "800",
                          "minNotionalValue": "5"},
    }})
    o = place_passive_order(
        book(), side="Buy", price=D("100"), quantity=D("0.05"),
        arrival_ts=1001, expiry_ts=5000, instrument_spec=spec, symbol="TESTUSDT",
    )
    assert o.quantity == D("0.05")


def test_passive_order_rejects_price_off_tick_from_exchange_spec():
    spec = InstrumentSpec.from_snapshot({"instrument": {
        "symbol": "TESTUSDT", "category": "linear", "status": "Trading",
        "priceFilter": {"minPrice": "0.1", "maxPrice": "1000000", "tickSize": "0.5"},
        "lotSizeFilter": {"qtyStep": "0.01", "minOrderQty": "0.01",
                          "maxOrderQty": "1000", "maxMktOrderQty": "800",
                          "minNotionalValue": "1"},
    }})
    try:
        place_passive_order(
            book(), side="Buy", price=D("100.2"), quantity=D("1"),
            arrival_ts=1001, expiry_ts=5000, instrument_spec=spec, symbol="TESTUSDT",
        )
    except ValueError as exc:
        assert "tickSize" in str(exc)
    else:
        raise AssertionError("off-tick passive price must be rejected")


def test_passive_order_rejects_quantity_off_step_instead_of_silently_rounding():
    spec = InstrumentSpec.from_snapshot({"instrument": {
        "symbol": "TESTUSDT", "category": "linear", "status": "Trading",
        "priceFilter": {"minPrice": "0.1", "maxPrice": "1000000", "tickSize": "0.1"},
        "lotSizeFilter": {"qtyStep": "0.05", "minOrderQty": "0.05",
                          "maxOrderQty": "1000", "maxMktOrderQty": "800",
                          "minNotionalValue": "1"},
    }})
    try:
        place_passive_order(
            book(), side="Buy", price=D("100"), quantity=D("0.06"),
            arrival_ts=1001, expiry_ts=5000, instrument_spec=spec, symbol="TESTUSDT",
        )
    except ValueError as exc:
        assert "qtyStep" in str(exc)
    else:
        raise AssertionError("off-step quantity must be rejected, not rounded")


def test_passive_order_rejects_below_exchange_min_order_qty():
    spec = InstrumentSpec.from_snapshot({"instrument": {
        "symbol": "TESTUSDT", "category": "linear", "status": "Trading",
        "priceFilter": {"minPrice": "0.1", "maxPrice": "1000000", "tickSize": "0.1"},
        "lotSizeFilter": {"qtyStep": "0.01", "minOrderQty": "0.1",
                          "maxOrderQty": "1000", "maxMktOrderQty": "800",
                          "minNotionalValue": "1"},
    }})
    try:
        place_passive_order(
            book(), side="Buy", price=D("100"), quantity=D("0.09"),
            arrival_ts=1001, expiry_ts=5000, instrument_spec=spec, symbol="TESTUSDT",
        )
    except ValueError as exc:
        assert "minOrderQty" in str(exc)
    else:
        raise AssertionError("below-minimum quantity must be rejected")


def test_passive_order_rejects_below_exchange_min_notional():
    spec = InstrumentSpec.from_snapshot({"instrument": {
        "symbol": "TESTUSDT", "category": "linear", "status": "Trading",
        "priceFilter": {"minPrice": "0.1", "maxPrice": "1000000", "tickSize": "0.1"},
        "lotSizeFilter": {"qtyStep": "0.01", "minOrderQty": "0.01",
                          "maxOrderQty": "1000", "maxMktOrderQty": "800",
                          "minNotionalValue": "10"},
    }})
    try:
        place_passive_order(
            book(), side="Buy", price=D("100"), quantity=D("0.09"),
            arrival_ts=1001, expiry_ts=5000, instrument_spec=spec, symbol="TESTUSDT",
        )
    except ValueError as exc:
        assert "minNotionalValue" in str(exc)
    else:
        raise AssertionError("below-minimum notional must be rejected")



def test_passive_order_rejects_instrument_spec_for_different_symbol():
    spec = InstrumentSpec.from_snapshot({"instrument": {
        "symbol": "ETHUSDT", "category": "linear", "status": "Trading",
        "priceFilter": {"minPrice": "0.1", "maxPrice": "1000000", "tickSize": "0.1"},
        "lotSizeFilter": {"qtyStep": "0.01", "minOrderQty": "0.01",
                          "maxOrderQty": "1000", "maxMktOrderQty": "800",
                          "minNotionalValue": "1"},
    }})
    try:
        place_passive_order(
            book(), side="Buy", price=D("100"), quantity=D("1"),
            arrival_ts=1001, expiry_ts=5000, instrument_spec=spec,
            symbol="BTCUSDT",
        )
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("instrument spec for another symbol must be rejected")


def test_passive_order_requires_symbol_when_spec_is_supplied():
    spec = InstrumentSpec.from_snapshot({"instrument": {
        "symbol": "TESTUSDT", "category": "linear", "status": "Trading",
        "priceFilter": {"minPrice": "0.1", "maxPrice": "1000000", "tickSize": "0.1"},
        "lotSizeFilter": {"qtyStep": "0.01", "minOrderQty": "0.01",
                          "maxOrderQty": "1000", "maxMktOrderQty": "800",
                          "minNotionalValue": "1"},
    }})
    try:
        place_passive_order(
            book(), side="Buy", price=D("100"), quantity=D("1"),
            arrival_ts=1001, expiry_ts=5000, instrument_spec=spec,
        )
    except ValueError as exc:
        assert "symbol is required" in str(exc)
    else:
        raise AssertionError("spec validation must require an explicit symbol")



def test_partial_fills_record_each_execution_and_calculate_vwap():
    o = order(qty="3")
    apply_public_trade(o, trade(1100, "Sell", "100", "6"))
    apply_public_trade(o, trade(1200, "Sell", "100", "2"))
    assert len(o.fills) == 2
    assert [fill.quantity for fill in o.fills] == [D("1"), D("2")]
    assert [fill.timestamp_ms for fill in o.fills] == [1100, 1200]
    assert o.filled_notional == D("300")
    assert o.filled_vwap == D("100")


def test_per_fill_fee_ledger_requires_explicit_rate_for_every_fill():
    o = order(qty="3")
    apply_public_trade(o, trade(1100, "Sell", "100", "6"))
    apply_public_trade(o, trade(1200, "Sell", "100", "2"))
    try:
        per_fill_fee_ledger(o, [D("0.0002")])
    except ValueError as exc:
        assert "one explicit maker fee rate" in str(exc)
    else:
        raise AssertionError("missing per-fill fee rate must fail closed")


def test_per_fill_fee_ledger_uses_each_supplied_rate_and_allows_explicit_rebate():
    o = order(qty="3")
    apply_public_trade(o, trade(1100, "Sell", "100", "6"))
    apply_public_trade(o, trade(1200, "Sell", "100", "2"))
    ledger = per_fill_fee_ledger(o, [D("0.0002"), D("-0.00001")])
    assert ledger[0]["notional"] == D("100")
    assert ledger[0]["fee"] == D("0.0200")
    assert ledger[1]["notional"] == D("200")
    assert ledger[1]["fee"] == D("-0.00200")



def test_post_fill_markouts_are_attached_to_each_partial_fill():
    fills = [
        {"timestamp_ms": 1000, "side": "Buy", "price": "100", "quantity": "1"},
        {"timestamp_ms": 2000, "side": "Buy", "price": "100", "quantity": "2"},
    ]
    result = {"fills": fills}
    original = l2_runner.capture_book_states_at
    def fake_states(_archive, targets):
        return {
            target: {
                "book_cts": target - 100,
                "bids": {D("100.1"): D("5")},
                "asks": {D("100.3"): D("5")},
            }
            for target in targets
        }
    l2_runner.capture_book_states_at = fake_states
    try:
        l2_runner.add_post_fill_markouts(Path("unused.zip"), [result])
    finally:
        l2_runner.capture_book_states_at = original
    assert len(fills[0]["post_fill_markout"]) == 4
    assert len(fills[1]["post_fill_markout"]) == 4
    assert D(fills[0]["post_fill_markout"][0]["signed_mid_markout_bps"]) == D("20")
    assert D(fills[1]["post_fill_markout"][0]["signed_mid_markout_bps"]) == D("20")


def test_no_fill_scenario_has_no_per_fill_markouts():
    result = {"fills": []}
    original = l2_runner.capture_book_states_at
    l2_runner.capture_book_states_at = lambda *_args: {}
    try:
        l2_runner.add_post_fill_markouts(Path("unused.zip"), [result])
    finally:
        l2_runner.capture_book_states_at = original
    assert result["fills"] == []



def test_order_book_rejects_float_update_id_without_truncating():
    b = book()
    before = (dict(b.bids), dict(b.asks), b.last_cts, b.last_seq, b.last_u)
    event = {
        "type": "delta", "cts": 1100,
        "data": {"seq": 2, "u": 2.9, "b": [["100", "4"]], "a": []},
    }
    try:
        b.apply(event)
    except ValueError as exc:
        assert "u must be an integer" in str(exc)
    else:
        raise AssertionError("float update ID must not be truncated")
    assert (b.bids, b.asks, b.last_cts, b.last_seq, b.last_u) == before


def test_order_book_rejects_boolean_sequence_number():
    b = book()
    event = {
        "type": "delta", "cts": 1100,
        "data": {"seq": True, "u": 2, "b": [["100", "4"]], "a": []},
    }
    try:
        b.apply(event)
    except ValueError as exc:
        assert "seq must be an integer" in str(exc)
    else:
        raise AssertionError("boolean seq must not be accepted")


def test_order_book_rejects_fractional_matching_engine_timestamp():
    b = book()
    event = {
        "type": "delta", "cts": 1100.5,
        "data": {"seq": 2, "u": 2, "b": [["100", "4"]], "a": []},
    }
    try:
        b.apply(event)
    except ValueError as exc:
        assert "cts must be an integer" in str(exc)
    else:
        raise AssertionError("fractional cts must not be truncated")



def test_order_book_rejects_delta_before_initial_snapshot():
    b = OrderBook()
    event = {
        "type": "delta", "cts": 1000,
        "data": {"seq": 1, "u": 2, "b": [["100", "5"]], "a": [["101", "6"]]},
    }
    try:
        b.apply(event)
    except ValueError as exc:
        assert "begin with a full snapshot" in str(exc)
    else:
        raise AssertionError("delta cannot initialize a reconstructed book")
    assert b.bids == {}
    assert b.asks == {}
    assert b.last_u is None


def test_snapshot_and_delta_are_absolute_level_updates_and_zero_deletes():
    b = book()
    b.apply({"type": "delta", "cts": 1100, "data": {
        "seq": 2, "u": 2, "b": [["100", "7"], ["99", "0"]],
        "a": [["101", "4"]],
    }})
    assert b.quantity_at("Buy", D("100")) == D("7")
    assert b.quantity_at("Buy", D("99")) == 0
    assert b.quantity_at("Sell", D("101")) == D("4")




def test_missing_orderbook_update_id_fails_closed():
    b = OrderBook()
    try:
        b.apply({"type": "snapshot", "cts": 1000, "data": {
            "seq": 1, "b": [["100", "5"]], "a": [["101", "5"]],
        }})
    except ValueError as exc:
        assert "u must be an integer" in str(exc)
    else:
        raise AssertionError("missing Bybit update ID must fail closed")



def test_duplicate_price_levels_in_snapshot_are_rejected_atomically():
    b = OrderBook()
    event = {
        "type": "snapshot", "cts": 1000,
        "data": {
            "seq": 1, "u": 1,
            "b": [["100", "5"], ["100", "7"]],
            "a": [["101", "6"]],
        },
    }
    try:
        b.apply(event)
    except ValueError as exc:
        assert "duplicate b price level" in str(exc)
    else:
        raise AssertionError("duplicate snapshot price levels must be rejected")
    assert b.bids == {}
    assert b.asks == {}
    assert b.last_cts is None


def test_duplicate_price_levels_in_delta_are_rejected_atomically():
    b = book()
    before = (dict(b.bids), dict(b.asks), b.last_cts, b.last_seq, b.last_u)
    event = {
        "type": "delta", "cts": 1100,
        "data": {
            "seq": 2, "u": 2,
            "b": [["100", "4"], ["100", "3"]],
            "a": [],
        },
    }
    try:
        b.apply(event)
    except ValueError as exc:
        assert "duplicate b price level" in str(exc)
    else:
        raise AssertionError("duplicate delta price levels must be rejected")
    assert (b.bids, b.asks, b.last_cts, b.last_seq, b.last_u) == before


def test_invalid_delta_is_atomic_and_does_not_partially_mutate_book():
    b = book()
    before = b.copy_levels()
    try:
        b.apply({"type": "delta", "cts": 1100, "data": {
            "seq": 2, "u": 2, "b": [["100", "7"], ["bad-price", "1"]], "a": [],
        }})
    except ValueError:
        pass
    else:
        raise AssertionError("malformed delta must fail")
    assert b.copy_levels() == before
    assert b.last_cts == 1000
    assert b.last_seq == 1
    assert b.last_u == 1


def test_invalid_snapshot_is_atomic_and_preserves_previous_book():
    b = book()
    before = b.copy_levels()
    try:
        b.apply({"type": "snapshot", "cts": 1100, "data": {
            "seq": 2, "u": 2, "b": [["98", "4"]], "a": "not-a-level-list",
        }})
    except ValueError:
        pass
    else:
        raise AssertionError("malformed snapshot must fail")
    assert b.copy_levels() == before
    assert b.last_cts == 1000
    assert b.last_seq == 1
    assert b.last_u == 1


def test_u1_restart_snapshot_replaces_book_and_preserves_cross_sequence_order():
    b = book()
    b.apply({"type": "delta", "cts": 1100, "data": {
        "u": 2, "seq": 2, "b": [["100", "7"]], "a": [],
    }})
    b.apply({"type": "snapshot", "cts": 1200, "data": {
        "u": 1, "seq": 3, "b": [["98", "4"]], "a": [["99", "6"]],
    }})
    assert b.last_u == 1
    assert b.last_seq == 3
    assert b.quantity_at("Buy", D("100")) == 0
    assert b.quantity_at("Buy", D("98")) == D("4")
    assert b.quantity_at("Sell", D("99")) == D("6")



def test_non_reset_orderbook_update_id_regression_fails_closed_atomically():
    b = book()
    b.apply({"type": "delta", "cts": 1100, "data": {
        "seq": 2, "u": 3, "b": [["100", "7"]], "a": [],
    }})
    before = (dict(b.bids), dict(b.asks), b.last_cts, b.last_seq, b.last_u)
    try:
        b.apply({"type": "delta", "cts": 1200, "data": {
            "seq": 3, "u": 2, "b": [["100", "9"]], "a": [],
        }})
    except ValueError as exc:
        assert "non-monotonic order-book update ID" in str(exc)
    else:
        raise AssertionError("non-reset update ID regression must fail closed")
    assert (b.bids, b.asks, b.last_cts, b.last_seq, b.last_u) == before


def test_u1_restart_snapshot_does_not_bypass_cross_sequence_ordering():
    b = book()
    b.apply({"type": "delta", "cts": 1050, "data": {
        "u": 2, "seq": 2, "b": [["100", "6"]], "a": [],
    }})
    try:
        b.apply({"type": "snapshot", "cts": 1100, "data": {
            "u": 1, "seq": 1, "b": [["98", "4"]], "a": [["99", "6"]],
        }})
    except ValueError as exc:
        assert "non-monotonic cross sequence" in str(exc)
    else:
        raise AssertionError("u=1 must not bypass cross-sequence ordering")


def test_u1_restart_marker_on_delta_fails_closed_without_mutating_book():
    b = book()
    before = b.copy_levels()
    try:
        b.apply({"type": "delta", "cts": 1100, "data": {
            "u": 1, "seq": 1, "b": [["100", "0"]], "a": [],
        }})
    except ValueError as exc:
        assert "requires a full snapshot" in str(exc)
    else:
        raise AssertionError("u=1 delta must not be applied as a complete book")
    assert b.copy_levels() == before
    assert b.last_u == 1


def test_passive_order_rejects_book_state_at_or_after_arrival():
    b = book()
    for cts in (1000, 1001):
        b.last_cts = cts
        try:
            place_passive_order(
                b, side="Buy", price=D("100"), quantity=D("1"),
                arrival_ts=1000, expiry_ts=5000,
            )
        except ValueError as exc:
            assert "strictly earlier" in str(exc)
        else:
            raise AssertionError("same-ms or future book state must not seed queue position")


def test_passive_order_rejects_book_without_timestamp():
    b = book()
    b.last_cts = None
    try:
        place_passive_order(
            b, side="Buy", price=D("100"), quantity=D("1"),
            arrival_ts=1000, expiry_ts=5000,
        )
    except ValueError as exc:
        assert "timestamped order-book state" in str(exc)
    else:
        raise AssertionError("untimestamped book must not seed queue position")


def test_passive_order_rejects_prices_beyond_visible_depth():
    for side, price, expected in (
        ("Buy", "98", "outside visible bid depth"),
        ("Sell", "103", "outside visible ask depth"),
    ):
        try:
            place_passive_order(
                book(), side=side, price=D(price), quantity=D("1"),
                arrival_ts=1001, expiry_ts=5000,
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("order beyond visible L2 depth must not assume zero queue")


def test_passive_order_accepts_empty_price_inside_visible_depth():
    buy = place_passive_order(
        book(), side="Buy", price=D("99.5"), quantity=D("1"),
        arrival_ts=1001, expiry_ts=5000,
    )
    sell = place_passive_order(
        book(), side="Sell", price=D("101.5"), quantity=D("1"),
        arrival_ts=1001, expiry_ts=5000,
    )
    assert buy.queue_ahead_initial == D("0")
    assert sell.queue_ahead_initial == D("0")


def test_buy_order_queue_ahead_is_initial_displayed_bid_size():
    o = order()
    assert o.queue_ahead_initial == D("5")
    assert o.queue_ahead_remaining == D("5")


def test_sell_order_queue_ahead_is_initial_displayed_ask_size():
    o = order(side="Sell", price="101")
    assert o.queue_ahead_initial == D("6")


def test_only_opposing_aggressor_trades_at_exact_price_consume_queue():
    o = order()
    apply_public_trade(o, trade(1100, "Buy", "100", "9"))
    apply_public_trade(o, trade(1200, "Sell", "99", "9"))
    assert o.queue_ahead_remaining == D("5")
    assert o.filled == 0
    apply_public_trade(o, trade(1300, "Sell", "100", "3"))
    assert o.queue_ahead_remaining == D("2")
    assert o.filled == 0


def test_fill_occurs_only_after_queue_ahead_is_consumed():
    o = order()
    apply_public_trade(o, trade(1100, "Sell", "100", "7"))
    assert o.queue_ahead_remaining == 0
    assert o.filled == D("2")
    assert o.complete


def test_partial_fill_and_later_completion():
    o = order(qty="3")
    apply_public_trade(o, trade(1100, "Sell", "100", "6"))
    assert o.filled == D("1")
    assert o.remaining == D("2")
    apply_public_trade(o, trade(1200, "Sell", "100", "2"))
    assert o.filled == D("3")
    assert o.complete



def test_trade_timestamp_parser_preserves_exact_seconds_and_milliseconds():
    assert l2_module.parse_trade_timestamp_ms("1756771200.123") == 1756771200123
    assert l2_module.parse_trade_timestamp_ms("1756771200123") == 1756771200123
    # Exactly 1e12 is the first value classified as epoch milliseconds.
    assert l2_module.parse_trade_timestamp_ms("1000000000000") == 1000000000000


def test_trade_timestamp_parser_rejects_submillisecond_rounding():
    try:
        l2_module.parse_trade_timestamp_ms("1756771200123.5")
    except ValueError as exc:
        assert "sub-millisecond" in str(exc)
    else:
        raise AssertionError("fractional milliseconds must not be rounded")


def test_trade_timestamp_parser_rejects_nonfinite_and_nonpositive_values():
    for value in ("NaN", "Infinity", "0", "-1", "not-a-time"):
        try:
            l2_module.parse_trade_timestamp_ms(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid timestamp accepted: {value}")


def test_apply_public_trade_rejects_fractional_timestamp_without_truncation():
    o = order()
    try:
        apply_public_trade(o, trade(1100.5, "Sell", "100", "10"))
    except ValueError as exc:
        assert "must be an integer" in str(exc)
    else:
        raise AssertionError("fractional timestamp must not be truncated")
    assert o.filled == D("0")
    assert o.queue_ahead_remaining == D("5")



def test_block_trade_does_not_consume_displayed_queue():
    o = order(qty="2")
    apply_public_trade(o, {**trade(1100, "Sell", "100", "10"), "block_trade": True})
    assert o.block_trade_excluded_count == 1
    assert o.queue_ahead_remaining == D("5")
    assert o.filled == D("0")
    assert o.eligible_trade_count == 0


def test_non_block_trade_still_consumes_queue_normally():
    o = order(qty="2")
    apply_public_trade(o, {**trade(1100, "Sell", "100", "6"), "block_trade": False})
    assert o.block_trade_excluded_count == 0
    assert o.queue_ahead_remaining == D("0")
    assert o.filled == D("1")


def test_missing_block_trade_flag_fails_closed():
    o = order()
    event = trade(1100, "Sell", "100", "10")
    event.pop("block_trade")
    try:
        apply_public_trade(o, event)
    except ValueError as exc:
        assert "block trade boolean flag" in str(exc)
    else:
        raise AssertionError("missing block-trade flag must fail closed")
    assert o.queue_ahead_remaining == D("5")
    assert o.filled == D("0")


def test_missing_rpi_flag_fails_closed():
    o = order()
    event = trade(1100, "Sell", "100", "10")
    event.pop("rpi")
    try:
        apply_public_trade(o, event)
    except ValueError as exc:
        assert "RPI boolean flag" in str(exc)
    else:
        raise AssertionError("missing RPI flag must fail closed")
    assert o.queue_ahead_remaining == D("5")
    assert o.filled == D("0")


def test_exchange_boolean_parser_rejects_float_coercion():
    for value in (0.0, 1.0):
        try:
            l2_module.parse_exchange_bool(value, "test")
        except ValueError:
            pass
        else:
            raise AssertionError(f"float boolean flag accepted: {value!r}")


def test_invalid_block_trade_flag_fails_closed():
    o = order()
    try:
        apply_public_trade(o, {**trade(1100, "Sell", "100", "10"), "block_trade": "unknown"})
    except ValueError as exc:
        assert "block trade boolean flag" in str(exc)
    else:
        raise AssertionError("unknown block-trade flag must fail closed")
    assert o.queue_ahead_remaining == D("5")
    assert o.filled == D("0")


def test_trade_archive_requires_block_trade_flag():
    import gzip
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trades.csv.gz"
        with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
            stream.write("timestamp,symbol,side,size,price,trdMatchID\n")
            stream.write("1756771200123,AAVEUSDT,Sell,10,100,match-1\n")
        try:
            list(l2_module.iter_public_trades(path))
        except ValueError as exc:
            assert "missing block-trade flag" in str(exc)
        else:
            raise AssertionError("archive without block-trade flag must fail closed")


def test_trade_archive_requires_rpi_flag():
    import gzip
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trades.csv.gz"
        with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
            stream.write("timestamp,symbol,side,size,price,trdMatchID,isBlockTrade\n")
            stream.write("1756771200123,AAVEUSDT,Sell,10,100,match-1,False\n")
        try:
            list(l2_module.iter_public_trades(path))
        except ValueError as exc:
            assert "missing RPI flag" in str(exc)
        else:
            raise AssertionError("archive without RPI flag must fail closed")

def test_trade_archive_rejects_duplicate_column_names():
    import gzip
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trades.csv.gz"
        with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
            stream.write("timestamp,symbol,side,size,price,trdMatchID,trdMatchID,isBlockTrade,RPI\\n")
            stream.write("1756771200123,AAVEUSDT,Sell,10,100,match-1,match-2,False,False\\n")
        try:
            list(l2_module.iter_public_trades(path))
        except ValueError as exc:
            assert "duplicate column names" in str(exc)
        else:
            raise AssertionError("duplicate CSV headers must be rejected")


def test_trade_archive_rejects_empty_or_whitespace_trade_id():
    import gzip
    for trade_id in ("", "   "):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trades.csv.gz"
            with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
                stream.write("timestamp,symbol,side,size,price,trdMatchID,isBlockTrade,RPI\n")
                stream.write(f"1756771200123,AAVEUSDT,Sell,10,100,{trade_id},False,False\n")
            try:
                list(l2_module.iter_public_trades(path))
            except ValueError as exc:
                assert "missing public trade ID" in str(exc)
            else:
                raise AssertionError("empty trade IDs must be rejected")


def test_trade_archive_rejects_extra_csv_fields():
    import gzip
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trades.csv.gz"
        with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
            stream.write("timestamp,symbol,side,size,price,trdMatchID,isBlockTrade,RPI\n")
            stream.write("1756771200123,AAVEUSDT,Sell,10,100,match-1,False,False,unexpected\n")
        try:
            list(l2_module.iter_public_trades(path))
        except ValueError as exc:
            assert "extra CSV fields" in str(exc)
        else:
            raise AssertionError("extra CSV fields must be rejected")


def test_trade_archive_rejects_trade_id_with_surrounding_whitespace():
    import gzip
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trades.csv.gz"
        with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
            stream.write("timestamp,symbol,side,size,price,trdMatchID,isBlockTrade,RPI\n")
            stream.write("1756771200123,AAVEUSDT,Sell,10,100, match-1 ,False,False\n")
        try:
            list(l2_module.iter_public_trades(path))
        except ValueError as exc:
            assert "surrounding whitespace" in str(exc)
        else:
            raise AssertionError("padded trade IDs must be rejected")


def test_trade_archive_rejects_conflicting_block_flag_aliases():
    import gzip
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trades.csv.gz"
        with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
            stream.write("timestamp,symbol,side,size,price,trdMatchID,isBlockTrade,BT,RPI\n")
            stream.write("1756771200123,AAVEUSDT,Sell,10,100,match-1,False,True,False\n")
        try:
            list(l2_module.iter_public_trades(path))
        except ValueError as exc:
            assert "conflicting block-trade flag aliases" in str(exc)
        else:
            raise AssertionError("conflicting block-trade aliases must be rejected")


def test_trade_archive_rejects_conflicting_rpi_flag_aliases():
    import gzip
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trades.csv.gz"
        with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
            stream.write("timestamp,symbol,side,size,price,trdMatchID,BT,RPI,isRPITrade\n")
            stream.write("1756771200123,AAVEUSDT,Sell,10,100,match-1,False,False,True\n")
        try:
            list(l2_module.iter_public_trades(path))
        except ValueError as exc:
            assert "conflicting RPI flag aliases" in str(exc)
        else:
            raise AssertionError("conflicting RPI aliases must be rejected")


def test_trade_archive_validates_side_price_and_size_for_every_row():
    import gzip
    cases = [
        ("Unknown", "100", "1", "invalid public trade side"),
        ("Sell", "0", "1", "price and size must be positive"),
        ("Buy", "100", "0", "price and size must be positive"),
    ]
    for side, price, size, expected in cases:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trades.csv.gz"
            with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
                stream.write("timestamp,symbol,side,size,price,trdMatchID,isBlockTrade,RPI\n")
                stream.write(f"1756771200123,AAVEUSDT,{side},{size},{price},match-1,False,False\n")
            try:
                list(l2_module.iter_public_trades(path))
            except ValueError as exc:
                assert expected in str(exc)
            else:
                raise AssertionError("invalid side/price/size must be rejected")


def test_trade_archive_parses_block_trade_and_rpi_flags():
    import gzip
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trades.csv.gz"
        with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
            stream.write("timestamp,symbol,side,size,price,trdMatchID,isBlockTrade,RPI\n")
            stream.write("1756771200.123,AAVEUSDT,Sell,10,100,match-1,True,False\n")
        rows = list(l2_module.iter_public_trades(path))
    assert rows[0]["timestamp_ms"] == 1756771200123
    assert rows[0]["block_trade"] is True
    assert rows[0]["rpi"] is False



def test_replay_rejects_fractional_timestamp_and_rolls_back_order():
    o = order(qty="2")
    events = [{**trade(1100.5, "Sell", "100", "10"), "trade_id": "bad-time"}]
    original = l2_module.iter_public_trades
    l2_module.iter_public_trades = lambda *_args: iter(events)
    try:
        try:
            l2_module.replay_public_trades(o, Path("unused.csv.gz"))
        except ValueError as exc:
            assert "must be an integer" in str(exc)
        else:
            raise AssertionError("fractional replay timestamp must fail closed")
    finally:
        l2_module.iter_public_trades = original
    assert o.queue_ahead_remaining == D("5")
    assert o.filled == D("0")
    assert o.processed_trade_ids == set()


def test_passive_order_rejects_fractional_arrival_timestamp():
    try:
        place_passive_order(
            book(), side="Buy", price=D("100"), quantity=D("1"),
            arrival_ts=1000.5, expiry_ts=5000,
        )
    except ValueError as exc:
        assert "arrival_ts must be an integer" in str(exc)
    else:
        raise AssertionError("fractional order arrival must fail closed")


def test_trade_at_or_before_arrival_is_never_credited():
    o = order()
    apply_public_trade(o, trade(1000, "Sell", "100", "100"))
    apply_public_trade(o, trade(999, "Sell", "100", "100"))
    assert o.filled == 0
    assert o.queue_ahead_remaining == D("5")


def test_expired_or_completed_order_ignores_later_trades():
    o = order(expiry=1200)
    apply_public_trade(o, trade(1200, "Sell", "100", "100"))
    assert o.filled == 0


def test_apply_public_trade_validates_normalized_rows_outside_active_window():
    expired = order()
    malformed_expired = {
        **trade(5000, "Sell", "100", "1"),
        "rpi": "unknown",
    }
    try:
        apply_public_trade(expired, malformed_expired)
    except ValueError as exc:
        assert "invalid RPI boolean flag" in str(exc)
    else:
        raise AssertionError("malformed normalized trade after expiry must fail closed")
    assert expired.filled == D("0")
    assert expired.queue_ahead_remaining == D("5")

    completed = order()
    apply_public_trade(completed, trade(1100, "Sell", "100", "6"))
    assert completed.complete
    malformed_completed = {
        **trade(1200, "Sell", "100", "1"),
        "block_trade": "unknown",
    }
    try:
        apply_public_trade(completed, malformed_completed)
    except ValueError as exc:
        assert "invalid block trade boolean flag" in str(exc)
    else:
        raise AssertionError("malformed normalized trade after completion must fail closed")
    assert completed.filled == D("5")


def test_rpi_trade_does_not_consume_queue_or_fill():
    o = order()
    apply_public_trade(o, trade(1100, "Sell", "100", "100", rpi="1"))
    assert o.filled == 0
    assert o.queue_ahead_remaining == D("5")
    assert o.rpi_excluded_count == 1


def test_unknown_trade_side_fails_even_when_trade_price_does_not_match():
    o = order()
    try:
        apply_public_trade(o, trade(1100, "Unknown", "99", "5"))
    except ValueError as exc:
        assert "unknown trade side" in str(exc)
    else:
        raise AssertionError("unknown trade side must fail closed")


def test_unknown_rpi_flag_fails_even_when_trade_price_does_not_match():
    o = order()
    try:
        apply_public_trade(o, trade(1100, "Sell", "99", "5", rpi="maybe"))
    except ValueError as exc:
        assert "invalid RPI boolean flag" in str(exc)
    else:
        raise AssertionError("unknown RPI flag must fail closed")


def test_non_positive_public_trade_price_or_size_fails_closed():
    o = order()
    for price, size in (("0", "1"), ("100", "0"), ("-1", "1"), ("100", "-1")):
        try:
            apply_public_trade(o, trade(1100, "Sell", price, size))
        except ValueError as exc:
            assert "must be positive" in str(exc)
        else:
            raise AssertionError("non-positive public trade values must fail closed")


def test_marketable_orders_are_rejected_from_maker_model():
    b = book()
    try:
        order(b, side="Buy", price="101")
    except ValueError as exc:
        assert "marketable" in str(exc)
    else:
        raise AssertionError("marketable buy should be rejected")
    try:
        order(b, side="Sell", price="100")
    except ValueError as exc:
        assert "marketable" in str(exc)
    else:
        raise AssertionError("marketable sell should be rejected")


def test_l2_cancellations_and_new_size_do_not_rewrite_existing_queue_ahead():
    b = book()
    o = order(b)
    # An L2 size reduction may be a cancellation, but cannot be assigned
    # to a position ahead of or behind our hypothetical order.
    b.apply({"type": "delta", "cts": 1100, "data": {
        "seq": 2, "u": 2, "b": [["100", "0"]], "a": [],
    }})
    assert b.quantity_at("Buy", D("100")) == 0
    assert o.queue_ahead_remaining == D("5")

    # New displayed size after our arrival is not added ahead of us.
    b.apply({"type": "delta", "cts": 1200, "data": {
        "seq": 3, "u": 3, "b": [["100", "9"]], "a": [],
    }})
    assert b.quantity_at("Buy", D("100")) == D("9")
    assert o.queue_ahead_remaining == D("5")


def test_non_monotonic_book_timestamp_is_rejected():
    b = book()
    try:
        b.apply({"type": "delta", "cts": 999, "data": {
            "seq": 2, "u": 2, "b": [], "a": [],
        }})
    except ValueError as exc:
        assert "non-monotonic" in str(exc)
    else:
        raise AssertionError("non-monotonic event should fail closed")


def test_buy_signed_markout_is_positive_when_mid_rises_after_fill():
    assert signed_markout_bps("Buy", D("100"), D("100.1"), D("100.3")) == D("20")


def test_sell_signed_markout_is_positive_when_mid_falls_after_fill():
    assert signed_markout_bps("Sell", D("100"), D("99.7"), D("99.9")) == D("20")



def test_duplicate_public_trade_id_fails_closed_before_double_counting():
    o = order(qty="3")
    events = [
        {**trade(1100, "Sell", "100", "6"), "trade_id": "match-1"},
        {**trade(1200, "Sell", "100", "6"), "trade_id": "match-1"},
    ]
    original = l2_module.iter_public_trades
    l2_module.iter_public_trades = lambda *_args: iter(events)
    try:
        try:
            l2_module.replay_public_trades(o, Path("unused.csv.gz"))
        except ValueError as exc:
            assert "duplicate public trade ID" in str(exc)
        else:
            raise AssertionError("duplicate trade ID must fail closed")
    finally:
        l2_module.iter_public_trades = original
    assert o.filled == D("0")
    assert o.queue_ahead_remaining == D("5")
    assert o.fills == []



def test_replay_rejects_out_of_order_trade_after_first_post_expiry_row():
    o = order(expiry=1150)
    events = [
        {**trade(1200, "Sell", "100", "10"), "trade_id": "after-expiry"},
        {**trade(1100, "Sell", "100", "10"), "trade_id": "inside-window"},
    ]
    original = l2_module.iter_public_trades
    l2_module.iter_public_trades = lambda *_args: iter(events)
    try:
        try:
            l2_module.replay_public_trades(o, Path("unused.csv.gz"))
        except ValueError as exc:
            assert "non-monotonic public trade timestamps" in str(exc)
        else:
            raise AssertionError("post-expiry row must not hide later out-of-order in-window trade")
    finally:
        l2_module.iter_public_trades = original
    assert o.filled == D("0")
    assert o.queue_ahead_remaining == D("5")
    assert o.processed_trade_ids == set()


def test_replay_checks_duplicate_ids_outside_order_active_window():
    o = order(expiry=1150)
    events = [
        {**trade(1200, "Sell", "100", "10"), "trade_id": "duplicate-outside"},
        {**trade(1300, "Sell", "100", "10"), "trade_id": "duplicate-outside"},
    ]
    original = l2_module.iter_public_trades
    l2_module.iter_public_trades = lambda *_args: iter(events)
    try:
        try:
            l2_module.replay_public_trades(o, Path("unused.csv.gz"))
        except ValueError as exc:
            assert "duplicate public trade ID" in str(exc)
        else:
            raise AssertionError("duplicate IDs anywhere in archive must fail closed")
    finally:
        l2_module.iter_public_trades = original
    assert o.filled == D("0")
    assert o.queue_ahead_remaining == D("5")
    assert o.processed_trade_ids == set()


def test_replaying_same_archive_twice_does_not_consume_queue_twice():
    o = order(qty="2")
    events = [{**trade(1100, "Sell", "100", "3"), "trade_id": "match-once"}]
    original = l2_module.iter_public_trades
    l2_module.iter_public_trades = lambda *_args: iter(events)
    try:
        l2_module.replay_public_trades(o, Path("unused.csv.gz"))
        assert o.queue_ahead_remaining == D("2")
        assert o.filled == D("0")
        l2_module.replay_public_trades(o, Path("unused.csv.gz"))
    finally:
        l2_module.iter_public_trades = original
    assert o.queue_ahead_remaining == D("2")
    assert o.filled == D("0")
    assert o.eligible_trade_count == 1
    assert o.processed_trade_ids == {("AAVEUSDT", "match-once")}


def test_missing_public_trade_id_fails_closed():
    o = order()
    events = [{**trade(1100, "Sell", "100", "6"), "trade_id": None}]
    original = l2_module.iter_public_trades
    l2_module.iter_public_trades = lambda *_args: iter(events)
    try:
        try:
            l2_module.replay_public_trades(o, Path("unused.csv.gz"))
        except ValueError as exc:
            assert "missing public trade ID" in str(exc)
        else:
            raise AssertionError("missing trade ID must fail closed")
    finally:
        l2_module.iter_public_trades = original
    assert o.filled == D("0")
    assert o.queue_ahead_remaining == D("5")


def test_orderbook_archive_rejects_duplicate_json_keys():
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "duplicate_json_key.zip"
        raw = (
            '{"type":"snapshot","cts":1000,"data":'
            '{"s":"AAVEUSDT","seq":1,"u":1,"u":2,'
            '"b":[["100","5"]],"a":[["101","5"]]}}'
        )
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("events.data", raw + chr(10))
        try:
            list(l2_module.iter_book_events(archive))
        except ValueError as exc:
            assert "duplicate JSON object key: u" in str(exc)
        else:
            raise AssertionError("duplicate JSON keys must be rejected")


def test_capture_book_at_rejects_fractional_cts_even_when_boundary_would_skip_event():
    events = [
        {"type": "snapshot", "cts": 1000, "data": {
            "s": "AAVEUSDT", "seq": 1, "u": 1,
            "b": [["100", "5"]], "a": [["101", "5"]],
        }},
        {"type": "delta", "cts": 2000.5, "data": {
            "s": "AAVEUSDT", "seq": 2, "u": 2,
            "b": [["100", "4"]], "a": [],
        }},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "fractional_cts.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("events.data", "".join(json.dumps(event) + chr(10) for event in events))
        try:
            capture_book_at(archive, 2000)
        except ValueError as exc:
            assert "invalid cts" in str(exc)
        else:
            raise AssertionError("fractional cts must not be skipped by int truncation")


def test_capture_book_at_rejects_out_of_order_event_after_arrival_boundary():
    events = [
        {"type": "snapshot", "cts": 1000, "data": {
            "s": "AAVEUSDT", "seq": 1, "u": 1,
            "b": [["100", "5"]], "a": [["101", "5"]],
        }},
        {"type": "delta", "cts": 3000, "data": {
            "s": "AAVEUSDT", "seq": 3, "u": 3,
            "b": [["100", "4"]], "a": [],
        }},
        {"type": "delta", "cts": 1500, "data": {
            "s": "AAVEUSDT", "seq": 2, "u": 2,
            "b": [["100", "3"]], "a": [],
        }},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "out_of_order_after_arrival.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("events.data", "".join(json.dumps(event) + chr(10) for event in events))
        try:
            capture_book_at(archive, 2000)
        except ValueError as exc:
            assert "non-monotonic cts" in str(exc)
        else:
            raise AssertionError("out-of-order event after arrival must invalidate archive")


def test_capture_book_at_rejects_seq_regression_after_arrival_boundary():
    events = [
        {"type": "snapshot", "cts": 1000, "data": {
            "s": "AAVEUSDT", "seq": 10, "u": 1,
            "b": [["100", "5"]], "a": [["101", "5"]],
        }},
        {"type": "delta", "cts": 3000, "data": {
            "s": "AAVEUSDT", "seq": 12, "u": 3,
            "b": [["100", "4"]], "a": [],
        }},
        {"type": "delta", "cts": 3500, "data": {
            "s": "AAVEUSDT", "seq": 11, "u": 4,
            "b": [["100", "3"]], "a": [],
        }},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "seq_regression_after_arrival.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("events.data", "".join(json.dumps(event) + chr(10) for event in events))
        try:
            capture_book_at(archive, 2000)
        except ValueError as exc:
            assert "non-monotonic seq" in str(exc)
        else:
            raise AssertionError("seq regression after arrival must invalidate archive")



def test_capture_book_at_rejects_malformed_book_events_after_arrival_boundary():
    cases = [
        {
            "type": "delta", "cts": 3_000, "data": {
                "s": "AAVEUSDT", "seq": 2, "u": "not-an-integer",
                "b": [["100", "4"]], "a": [],
            },
        },
        {
            "type": "delta", "cts": 3_000, "data": {
                "s": "AAVEUSDT", "seq": 2, "u": 2,
                "b": [["102", "4"]], "a": [],
            },
        },
    ]
    for index, malformed in enumerate(cases):
        events = [
            {
                "type": "snapshot", "cts": 1_000, "data": {
                    "s": "AAVEUSDT", "seq": 1, "u": 1,
                    "b": [["100", "5"]], "a": [["101", "5"]],
                },
            },
            malformed,
        ]
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / f"malformed_tail_{index}.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("events.data", "".join(json.dumps(event) + chr(10) for event in events))
            try:
                capture_book_at(archive, 2_000)
            except ValueError:
                pass
            else:
                raise AssertionError("malformed post-arrival book event must invalidate archive")



def test_capture_book_at_rejects_non_integer_arrival_timestamp():
    try:
        capture_book_at(Path("unused.zip"), 2000.5)
    except ValueError as exc:
        assert "arrival_ts" in str(exc)
    else:
        raise AssertionError("fractional arrival timestamp must be rejected")


def test_book_state_capture_excludes_same_millisecond_updates():
    events = [
        {"type": "snapshot", "cts": 1000, "data": {
            "s": "AAVEUSDT", "seq": 1, "u": 1,
            "b": [["100", "5"]], "a": [["101", "5"]],
        }},
        {"type": "delta", "cts": 2000, "data": {
            "s": "AAVEUSDT", "seq": 2, "u": 2,
            "b": [["100", "1"]], "a": [],
        }},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "same_ms.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("events.data", "".join(json.dumps(event) + chr(10) for event in events))
        book_state, observed_ts = capture_book_at(archive, 2000)
    assert observed_ts == 1000
    assert book_state.quantity_at("Buy", D("100")) == D("5")


def test_markout_state_capture_rejects_non_integer_targets():
    original = l2_runner.iter_book_events
    l2_runner.iter_book_events = lambda *_args: iter([])
    try:
        for target in (1000.5, True, "1000"):
            try:
                l2_runner.capture_book_states_at(Path("unused.zip"), [target])
            except ValueError as exc:
                assert "markout target timestamp" in str(exc)
            else:
                raise AssertionError("non-integer markout target must be rejected")
        try:
            l2_runner.capture_book_states_at(Path("unused.zip"), [0])
        except ValueError as exc:
            assert "must be positive" in str(exc)
        else:
            raise AssertionError("zero markout target must be rejected")
    finally:
        l2_runner.iter_book_events = original


def test_post_fill_markout_snapshot_excludes_same_millisecond_updates():
    events = [
        {"type": "snapshot", "cts": 1000, "data": {
            "s": "AAVEUSDT", "seq": 1, "u": 1,
            "b": [["100", "5"]], "a": [["101", "5"]],
        }},
        {"type": "delta", "cts": 2000, "data": {
            "s": "AAVEUSDT", "seq": 2, "u": 2,
            "b": [["100", "1"]], "a": [],
        }},
    ]
    original = l2_runner.iter_book_events
    l2_runner.iter_book_events = lambda *_args: iter(events)
    try:
        states = l2_runner.capture_book_states_at(Path("unused.zip"), [2000])
    finally:
        l2_runner.iter_book_events = original
    assert states[2000]["book_cts"] == 1000
    assert states[2000]["bids"][D("100")] == D("5")


if __name__ == "__main__":
    tests = [value for name, value in globals().copy().items()
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"{len(tests)}/{len(tests)} tests passed")
