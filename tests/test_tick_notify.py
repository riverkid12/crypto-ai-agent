from datetime import datetime, timedelta, timezone
import pytest
from adapters.exchanges._fake import FakeExchange
from adapters.notify.base import FakeNotifier
from db.repos.signals import Signals
from db.repos.strategies import Strategies
from executor.tick import run_tick


def _future_iso(hours=24):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _setup_strategy(db, universe):
    Strategies(db).insert(name="trend_majors", params={"universe": universe})


def test_fill_emits_info_notification(db):
    _setup_strategy(db, universe=["BTCUSDT"])
    Signals(db).insert(
        strategy_id=1, symbol="BTCUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTCUSDT", 60000.0)
    notifier = FakeNotifier()
    run_tick(db, ex, notifier=notifier, strategy_name="trend_majors")
    fills = [n for n in notifier.sent if n.type == "fill"]
    assert len(fills) == 1
    assert fills[0].severity == "info"
    assert fills[0].payload["symbol"] == "BTCUSDT"


def test_blocked_emits_info_notification(db):
    _setup_strategy(db, universe=["BTCUSDT"])
    Signals(db).insert(
        strategy_id=1, symbol="DOGEUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    notifier = FakeNotifier()
    run_tick(db, ex, notifier=notifier, strategy_name="trend_majors")
    blocked = [n for n in notifier.sent if n.type == "blocked"]
    assert len(blocked) == 1
    assert blocked[0].severity == "info"


def test_error_emits_error_notification(db):
    _setup_strategy(db, universe=["BTC"])
    Signals(db).insert(
        strategy_id=1, symbol="BTC", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    ex.fail_next_n_orders(1)
    notifier = FakeNotifier()
    run_tick(db, ex, notifier=notifier, strategy_name="trend_majors")
    errors = [n for n in notifier.sent if n.type == "error"]
    assert len(errors) == 1
    assert errors[0].severity == "error"


def test_no_notifier_doesnt_break(db):
    """tick.py without notifier should still work (None default)."""
    _setup_strategy(db, universe=["BTCUSDT"])
    Signals(db).insert(
        strategy_id=1, symbol="BTCUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTCUSDT", 60000.0)
    summary = run_tick(db, ex, strategy_name="trend_majors")  # no notifier
    assert summary["triggered"] == 1


def test_notifier_failure_doesnt_break_tick(db):
    """If notifier.send fails, tick still completes successfully."""
    _setup_strategy(db, universe=["BTCUSDT"])
    Signals(db).insert(
        strategy_id=1, symbol="BTCUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTCUSDT", 60000.0)
    notifier = FakeNotifier(fail=True)
    summary = run_tick(db, ex, notifier=notifier, strategy_name="trend_majors")
    assert summary["triggered"] == 1
    assert len(notifier.sent) >= 1


def test_fill_notification_includes_portfolio_md(db):
    """fill events get _portfolio_md attached."""
    _setup_strategy(db, universe=["BTCUSDT"])
    Signals(db).insert(
        strategy_id=1, symbol="BTCUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTCUSDT", 60000.0)
    notifier = FakeNotifier()
    run_tick(db, ex, notifier=notifier, strategy_name="trend_majors")
    fills = [n for n in notifier.sent if n.type == "fill"]
    assert len(fills) == 1
    # Snapshot must be attached
    assert "_portfolio_md" in fills[0].payload
    assert "BTCUSDT" in fills[0].payload["_portfolio_md"]


def test_error_notification_does_not_include_portfolio_md(db):
    """error events do NOT get portfolio (debug noise reduction)."""
    _setup_strategy(db, universe=["BTC"])
    Signals(db).insert(
        strategy_id=1, symbol="BTC", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    ex.fail_next_n_orders(1)
    notifier = FakeNotifier()
    run_tick(db, ex, notifier=notifier, strategy_name="trend_majors")
    errors = [n for n in notifier.sent if n.type == "error"]
    assert len(errors) >= 1
    # Snapshot must NOT be in any error payload
    for e in errors:
        assert "_portfolio_md" not in e.payload
