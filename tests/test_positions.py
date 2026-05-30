from db.repos.positions import Positions


def test_upsert_inserts_new(db):
    p = Positions(db)
    p.upsert("BTCUSDT", qty=0.01, avg_entry=60000.0)
    got = p.get("BTCUSDT")
    assert got is not None
    assert got.qty == 0.01
    assert got.avg_entry == 60000.0


def test_upsert_overwrites_existing(db):
    p = Positions(db)
    p.upsert("BTC", qty=0.01, avg_entry=60000.0)
    p.upsert("BTC", qty=0.02, avg_entry=61000.0)
    got = p.get("BTC")
    assert got.qty == 0.02
    assert got.avg_entry == 61000.0


def test_list_all_returns_all_symbols(db):
    p = Positions(db)
    p.upsert("BTC", qty=0.01, avg_entry=60000.0)
    p.upsert("ETH", qty=0.5, avg_entry=3000.0)
    syms = {pos.symbol for pos in p.list_all()}
    assert syms == {"BTC", "ETH"}


def test_count_open(db):
    p = Positions(db)
    assert p.count_open() == 0
    p.upsert("BTC", qty=0.01, avg_entry=60000.0)
    p.upsert("ETH", qty=0.5, avg_entry=3000.0)
    assert p.count_open() == 2


def test_get_qty_for_symbol(db):
    p = Positions(db)
    assert p.get_qty("BTC") == 0.0
    p.upsert("BTC", qty=0.01, avg_entry=60000.0)
    assert p.get_qty("BTC") == 0.01


def test_delete_closes_position(db):
    p = Positions(db)
    p.upsert("BTC", qty=0.01, avg_entry=60000.0)
    p.delete("BTC")
    assert p.get("BTC") is None
    assert p.count_open() == 0
