import pytest
from db.repos.control import Control
from db.repos.positions import Positions
from db.repos.events import Events
from executor.circuit_breaker import CircuitBreaker


@pytest.fixture
def cb(db):
    return CircuitBreaker(Control(db), Positions(db), Events(db))


def test_default_allows_entry(db, cb):
    assert cb.evaluate_new_entry(
        symbol="BTCUSDT", size_usdt=500.0,
        universe=["BTCUSDT"], daily_realized_pnl=0.0,
    ) is None


def test_kill_switch_blocks_entry(db, cb):
    Control(db).set("kill_switch", "true")
    reason = cb.evaluate_new_entry(
        symbol="BTCUSDT", size_usdt=500.0,
        universe=["BTCUSDT"], daily_realized_pnl=0.0,
    )
    assert reason is not None and "kill_switch" in reason.lower()


def test_size_above_cap_blocks(db, cb):
    reason = cb.evaluate_new_entry(
        symbol="BTC", size_usdt=501.0,
        universe=["BTC"], daily_realized_pnl=0.0,
    )
    assert reason is not None and "max_per_trade" in reason.lower()


def test_symbol_not_in_universe_blocks(db, cb):
    reason = cb.evaluate_new_entry(
        symbol="DOGE", size_usdt=100.0,
        universe=["BTC", "ETH"], daily_realized_pnl=0.0,
    )
    assert reason is not None and "universe" in reason.lower()


def test_daily_loss_breach_blocks_and_sets_kill_switch(db, cb):
    reason = cb.evaluate_new_entry(
        symbol="BTC", size_usdt=100.0,
        universe=["BTC"], daily_realized_pnl=-300.01,
    )
    assert reason is not None and "daily_loss" in reason.lower()
    assert Control(db).get_bool("kill_switch", default=False) is True


def test_max_open_positions_blocks(db, cb):
    Positions(db).upsert("BTC", qty=0.01, avg_entry=60000.0)
    Positions(db).upsert("ETH", qty=0.5, avg_entry=3000.0)
    Positions(db).upsert("SOL", qty=10, avg_entry=150.0)
    reason = cb.evaluate_new_entry(
        symbol="ADA", size_usdt=100.0,
        universe=["BTC", "ETH", "SOL", "ADA"], daily_realized_pnl=0.0,
    )
    assert reason is not None and "max_open_positions" in reason.lower()


def test_per_symbol_cap_blocks_adding(db, cb):
    Positions(db).upsert("BTC", qty=0.01, avg_entry=60000.0)
    reason = cb.evaluate_new_entry(
        symbol="BTC", size_usdt=100.0,
        universe=["BTC"], daily_realized_pnl=0.0,
    )
    assert reason is not None
    assert "max_position_per_symbol" in reason.lower()


def test_slippage_above_cap_blocks(db, cb):
    assert cb.check_slippage(0.011) is not None
    assert cb.check_slippage(0.009) is None


def test_risk_reduction_always_allowed(db, cb):
    Control(db).set("kill_switch", "true")
    assert cb.evaluate_risk_reduction() is None


def test_api_failure_circuit(db, cb):
    assert cb.should_circuit_open("BTC") is False
    cb.note_api_failure("BTC")
    cb.note_api_failure("BTC")
    assert cb.should_circuit_open("BTC") is False
    cb.note_api_failure("BTC")
    assert cb.should_circuit_open("BTC") is True


def test_api_success_resets_circuit(db, cb):
    """note_api_success clears the failure count (not decrement)."""
    cb.note_api_failure("BTC")
    cb.note_api_failure("BTC")
    cb.note_api_failure("BTC")
    assert cb.should_circuit_open("BTC") is True
    cb.note_api_success("BTC")
    assert cb.should_circuit_open("BTC") is False


def test_per_symbol_cap_relaxed_allows_adding(db, cb):
    """Setting max_position_per_symbol > 1 allows adding to existing position."""
    Control(db).set("max_position_per_symbol", "2")
    Positions(db).upsert("BTC", qty=0.01, avg_entry=60000.0)
    reason = cb.evaluate_new_entry(
        symbol="BTC", size_usdt=100.0,
        universe=["BTC"], daily_realized_pnl=0.0,
    )
    assert reason is None
