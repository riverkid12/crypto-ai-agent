import json
from db.repos.strategies import Strategies, Strategy


def test_insert_and_get_by_name(db):
    s = Strategies(db)
    sid = s.insert(name="trend_majors", params={"universe": ["BTCUSDT", "ETHUSDT"]})
    assert sid > 0
    got = s.get_by_name("trend_majors")
    assert got is not None
    assert got.id == sid
    assert got.name == "trend_majors"
    assert got.params == {"universe": ["BTCUSDT", "ETHUSDT"]}
    assert got.active is True


def test_get_by_name_missing_returns_none(db):
    s = Strategies(db)
    assert s.get_by_name("nope") is None


def test_list_active(db):
    s = Strategies(db)
    s.insert(name="a", params={"x": 1})
    s.insert(name="b", params={"y": 2})
    s.set_active("b", False)
    active = s.list_active()
    names = [st.name for st in active]
    assert names == ["a"]
