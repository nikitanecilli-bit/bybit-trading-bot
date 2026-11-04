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
    OrderBook, apply_public_trade, capture_book_at, place_passive_order, signed_markout_bps,
)


def book():
    b = OrderBook()
    b.apply({
        "type": "snapshot", "cts": 1000,
        "data": {"seq": 1, "u": 1, "b": [["100", "5"], ["99", "8"]],
                 "a": [["101", "6"], ["102", "9"]]},
    })
    return b


def order(b=None, side="Buy", price="100", qty="2", arrival=1000, expiry=5000):
    return place_passive_order(
        b or book(), side=side, price=D(price), quantity=D(qty),
        arrival_ts=arrival, expiry_ts=expiry,
    )


def trade(ts, side, price, size, rpi="0"):
    return {"timestamp_ms": ts, "side": side, "price": price, "size": size, "rpi": rpi}




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
        arrival_ts=1000, expiry_ts=5000, instrument_spec=spec, symbol="TESTUSDT",
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
            arrival_ts=1000, expiry_ts=5000, instrument_spec=spec,
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
            arrival_ts=1000, expiry_ts=5000, instrument_spec=spec,
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
            arrival_ts=1000, expiry_ts=5000, instrument_spec=spec,
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
            arrival_ts=1000, expiry_ts=5000, instrument_spec=spec,
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
            arrival_ts=1000, expiry_ts=5000, instrument_spec=spec,
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
            arrival_ts=1000, expiry_ts=5000, instrument_spec=spec,
        )
    except ValueError as exc:
        assert "symbol is required" in str(exc)
    else:
        raise AssertionError("spec validation must require an explicit symbol")


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
        assert "update ID" in str(exc)
    else:
        raise AssertionError("missing Bybit update ID must fail closed")



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



def test_u1_restart_snapshot_does_not_bypass_cross_sequence_ordering():
    b = book()
    try:
        b.apply({"type": "snapshot", "cts": 1100, "data": {
            "u": 1, "seq": 0, "b": [["98", "4"]], "a": [["99", "6"]],
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
        assert "unknown RPI flag" in str(exc)
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
    o = order()
    events = [
        {**trade(1100, "Sell", "100", "3"), "trade_id": "match-1"},
        {**trade(1200, "Sell", "100", "3"), "trade_id": "match-1"},
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
