from db.repos.orders import Orders, Order


def test_insert_and_get(db):
    o = Orders(db)
    oid = o.insert(
        signal_id=None, exchange_order_id="ex-1",
        symbol="BTCUSDT", side="buy", qty=0.01, price=60000.0,
        type="market", status="new",
    )
    assert oid > 0
    got = o.get(oid)
    assert got.symbol == "BTCUSDT"
    assert got.fill_qty == 0.0
    assert got.status == "new"


def test_update_fill_marks_filled(db):
    o = Orders(db)
    oid = o.insert(
        signal_id=None, exchange_order_id="ex-1",
        symbol="BTC", side="buy", qty=0.01, price=None,
        type="market", status="new",
    )
    o.update_fill(oid, fill_qty=0.01, fill_price=60100.0, fee_usdt=0.6, status="filled")
    got = o.get(oid)
    assert got.status == "filled"
    assert got.fill_qty == 0.01
    assert got.fill_price == 60100.0
    assert got.fee_usdt == 0.6
    assert got.filled_at is not None


def test_mark_failed_sets_status(db):
    o = Orders(db)
    oid = o.insert(
        signal_id=None, exchange_order_id=None,
        symbol="BTC", side="buy", qty=0.01, price=None,
        type="market", status="new",
    )
    o.mark_failed(oid)
    got = o.get(oid)
    assert got.status == "failed"
