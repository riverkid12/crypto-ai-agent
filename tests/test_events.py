import json
from db.repos.events import Events


def test_log_inserts_event(db):
    e = Events(db)
    e.log("signal_in", {"symbol": "BTC", "size": 500})
    rows = db.query("SELECT type, payload_json FROM events")
    assert len(rows) == 1
    assert rows[0][0] == "signal_in"
    assert json.loads(rows[0][1]) == {"symbol": "BTC", "size": 500}


def test_recent_returns_latest_first(db):
    e = Events(db)
    e.log("a", {})
    e.log("b", {})
    e.log("c", {})
    types = [ev.type for ev in e.recent(limit=2)]
    assert types == ["c", "b"]


def test_count_since_filters_by_time(db):
    e = Events(db)
    e.log("error", {})
    e.log("ok", {})
    e.log("error", {})
    assert e.count_since("error", "2000-01-01T00:00:00+00:00") == 2
