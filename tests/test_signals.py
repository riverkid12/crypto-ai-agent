from datetime import datetime, timedelta, timezone
from db.repos.signals import Signals, Signal
from db.repos.strategies import Strategies


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _future_iso(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _past_iso(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def test_insert_and_list_active(db):
    st = Strategies(db)
    sid = st.insert(name="s1", params={})
    sig = Signals(db)
    signal_id = sig.insert(
        strategy_id=sid, symbol="BTCUSDT", side="long",
        entry_price=60000.0, stop_price=58000.0, target_price=65000.0,
        size_usdt=500.0, expires_at=_future_iso(24), reason="test",
    )
    assert signal_id > 0
    active = sig.list_active()
    assert len(active) == 1
    assert active[0].symbol == "BTCUSDT"
    assert active[0].status == "pending"


def test_list_active_excludes_expired(db):
    st = Strategies(db)
    sid = st.insert(name="s1", params={})
    sig = Signals(db)
    sig.insert(
        strategy_id=sid, symbol="BTC", side="long", entry_price=None,
        stop_price=None, target_price=None, size_usdt=100.0,
        expires_at=_past_iso(1), reason="old",
    )
    assert sig.list_active() == []


def test_list_active_excludes_non_pending(db):
    st = Strategies(db)
    sid = st.insert(name="s1", params={})
    sig = Signals(db)
    s1 = sig.insert(
        strategy_id=sid, symbol="BTC", side="long", entry_price=None,
        stop_price=None, target_price=None, size_usdt=100.0,
        expires_at=_future_iso(24), reason="",
    )
    sig.mark_triggered(s1)
    assert sig.list_active() == []


def test_mark_triggered_sets_status(db):
    st = Strategies(db)
    sid = st.insert(name="s1", params={})
    sig = Signals(db)
    s1 = sig.insert(
        strategy_id=sid, symbol="BTC", side="long", entry_price=None,
        stop_price=None, target_price=None, size_usdt=100.0,
        expires_at=_future_iso(24), reason="",
    )
    sig.mark_triggered(s1)
    assert sig.get(s1).status == "triggered"
