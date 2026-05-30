import pytest
from adapters.exchanges._fake import FakeExchange


def test_get_price_returns_set_value():
    ex = FakeExchange()
    ex.set_price("BTCUSDT", 60000.0)
    assert ex.get_price("BTCUSDT") == 60000.0


def test_get_price_unknown_symbol_raises():
    ex = FakeExchange()
    with pytest.raises(KeyError):
        ex.get_price("UNKNOWN")


def test_market_buy_fills_at_current_price():
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    order = ex.place_order("BTC", "buy", qty=0.01, type="market")
    assert order.status == "filled"
    assert order.fill_qty == 0.01
    assert order.fill_price == 60000.0
    assert order.id.startswith("fake-")
    assert order.fee_usdt > 0  # 預設費率 > 0


def test_market_sell_fills_at_current_price():
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    order = ex.place_order("BTC", "sell", qty=0.01, type="market")
    assert order.status == "filled"
    assert order.fill_qty == 0.01


def test_orders_have_unique_ids():
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    a = ex.place_order("BTC", "buy", qty=0.01)
    b = ex.place_order("BTC", "buy", qty=0.01)
    assert a.id != b.id


def test_cancel_returns_false_for_unknown():
    ex = FakeExchange()
    assert ex.cancel("nope") is False


def test_set_failure_makes_next_order_fail():
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    ex.fail_next_n_orders(1)
    order = ex.place_order("BTC", "buy", qty=0.01)
    assert order.status == "failed"
    # 失敗扣完了,下一單恢復
    order2 = ex.place_order("BTC", "buy", qty=0.01)
    assert order2.status == "filled"
