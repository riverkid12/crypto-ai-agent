from datetime import datetime, timedelta, timezone
import pytest
from adapters.exchanges._fake import FakeExchange
from db.repos.control import Control
from db.repos.events import Events
from db.repos.orders import Orders
from db.repos.positions import Positions
from db.repos.signals import Signals
from db.repos.strategies import Strategies
from executor.circuit_breaker import CircuitBreaker
from executor.tick import run_tick


def _future_iso(hours=24):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _setup_strategy(db, universe):
    Strategies(db).insert(name="trend_majors", params={"universe": universe})


def test_market_signal_results_in_order_and_position(db):
    _setup_strategy(db, universe=["BTCUSDT"])
    Signals(db).insert(
        strategy_id=1, symbol="BTCUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=300.0, expires_at=_future_iso(), reason="market entry test",
    )
    ex = FakeExchange()
    ex.set_price("BTCUSDT", 60000.0)

    summary = run_tick(db, ex, strategy_name="trend_majors")

    assert summary["triggered"] == 1
    assert summary["blocked"] == 0
    pos = Positions(db).get("BTCUSDT")
    assert pos is not None
    assert pos.qty == pytest.approx(300.0 / 60000.0)
    assert pos.avg_entry == 60000.0


def test_signal_outside_universe_is_blocked(db):
    _setup_strategy(db, universe=["BTCUSDT"])
    Signals(db).insert(
        strategy_id=1, symbol="DOGEUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    summary = run_tick(db, ex, strategy_name="trend_majors")
    assert summary["triggered"] == 0
    assert summary["blocked"] == 1


def test_kill_switch_blocks_all_entries(db):
    _setup_strategy(db, universe=["BTC"])
    Control(db).set("kill_switch", "true")
    Signals(db).insert(
        strategy_id=1, symbol="BTC", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    summary = run_tick(db, ex, strategy_name="trend_majors")
    assert summary["triggered"] == 0
    assert summary["blocked"] == 1


def test_failed_order_does_not_create_position(db):
    _setup_strategy(db, universe=["BTC"])
    Signals(db).insert(
        strategy_id=1, symbol="BTC", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    ex.fail_next_n_orders(1)
    summary = run_tick(db, ex, strategy_name="trend_majors")
    assert summary["triggered"] == 0
    assert summary["api_errors"] == 1
    assert Positions(db).get("BTC") is None


def test_circuit_open_skips_symbol_after_threshold(db):
    """3 consecutive place_order failures should trip the circuit; 4th signal blocked."""
    _setup_strategy(db, universe=["BTC"])
    for i in range(4):
        Signals(db).insert(
            strategy_id=1, symbol="BTC", side="long",
            entry_price=None, stop_price=None, target_price=None,
            size_usdt=100.0, expires_at=_future_iso(), reason=f"sig{i}",
        )
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    ex.fail_next_n_orders(3)  # first 3 place_orders return failed status
    summary = run_tick(db, ex, strategy_name="trend_majors")
    # 3 fails accumulate -> 4th signal hits circuit_open guard
    assert summary["api_errors"] == 3
    assert summary["blocked"] == 1
    assert summary["triggered"] == 0
