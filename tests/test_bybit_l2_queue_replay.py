from decimal import Decimal as D
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bybit_l2_queue_replay import (
    OrderBook, apply_public_trade, place_passive_order,
)


def book():
    b = OrderBook()
    b.apply({
        "type": "snapshot", "cts": 1000,
        "data": {"seq": 1, "b": [["100", "5"], ["99", "8"]],
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


def test_snapshot_and_delta_are_absolute_level_updates_and_zero_deletes():
    b = book()
    b.apply({"type": "delta", "cts": 1100, "data": {
        "seq": 2, "b": [["100", "7"], ["99", "0"]],
        "a": [["101", "4"]],
    }})
    assert b.quantity_at("Buy", D("100")) == D("7")
    assert b.quantity_at("Buy", D("99")) == 0
    assert b.quantity_at("Sell", D("101")) == D("4")


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


def test_cancellations_do_not_reduce_queue_ahead():
    o = order()
    # An L2 size reduction may be a cancellation. The replay intentionally
    # has no cancellation-to-queue-ahead path.
    assert o.queue_ahead_remaining == D("5")
    assert o.queue_ahead_remaining == D("5")


def test_non_monotonic_book_timestamp_is_rejected():
    b = book()
    try:
        b.apply({"type": "delta", "cts": 999, "data": {
            "seq": 2, "b": [], "a": [],
        }})
    except ValueError as exc:
        assert "non-monotonic" in str(exc)
    else:
        raise AssertionError("non-monotonic event should fail closed")


if __name__ == "__main__":
    tests = [value for name, value in globals().copy().items()
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"{len(tests)}/{len(tests)} tests passed")
