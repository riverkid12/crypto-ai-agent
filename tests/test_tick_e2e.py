from datetime import datetime, timedelta, timezone
from adapters.exchanges._fake import FakeExchange
from db.repos.control import Control
from db.repos.events import Events
from db.repos.positions import Positions
from db.repos.signals import Signals
from db.repos.strategies import Strategies
from executor.circuit_breaker import CircuitBreaker
from executor.tick import run_tick


def _future(hours=24):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def test_e2e_mixed_outcomes(db):
    """三筆 signal:
       - BTC market entry → 應該成交
       - ETH 標的不在 universe → 應該被擋
       - SOL price 低於 entry → 應該不觸發(matcher 擋,計入 'untriggered' 而非 'blocked')
    """
    universe = ["BTCUSDT", "SOLUSDT"]
    Strategies(db).insert(name="trend_majors", params={"universe": universe})

    Signals(db).insert(
        strategy_id=1, symbol="BTCUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=300.0, expires_at=_future(), reason="market BTC",
    )
    Signals(db).insert(
        strategy_id=1, symbol="ETHUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=300.0, expires_at=_future(), reason="outside universe",
    )
    Signals(db).insert(
        strategy_id=1, symbol="SOLUSDT", side="long",
        entry_price=200.0, stop_price=180.0, target_price=240.0,
        size_usdt=300.0, expires_at=_future(), reason="needs breakout",
    )

    ex = FakeExchange()
    ex.set_price("BTCUSDT", 60000.0)
    ex.set_price("ETHUSDT", 3000.0)
    ex.set_price("SOLUSDT", 150.0)  # 低於 entry 200

    summary = run_tick(db, ex, strategy_name="trend_majors")

    assert summary["triggered"] == 1
    assert summary["blocked"] == 1
    assert summary["api_errors"] == 0

    # BTC 有部位
    btc = Positions(db).get("BTCUSDT")
    assert btc is not None
    assert btc.qty > 0

    # ETH 沒部位
    assert Positions(db).get("ETHUSDT") is None

    # SOL 沒部位(matcher 沒觸發)
    assert Positions(db).get("SOLUSDT") is None

    # 應有對應 events
    events = Events(db)
    fills = [e for e in events.recent(50) if e.type == "fill"]
    blocks = [e for e in events.recent(50) if e.type == "blocked"]
    assert len(fills) == 1
    assert fills[0].payload["symbol"] == "BTCUSDT"
    assert len(blocks) == 1
    assert blocks[0].payload["symbol"] == "ETHUSDT"
    assert "universe" in blocks[0].payload["reason"].lower()


def test_e2e_kill_switch_after_daily_loss(db):
    universe = ["BTC"]
    Strategies(db).insert(name="trend_majors", params={"universe": universe})
    Signals(db).insert(
        strategy_id=1, symbol="BTC", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future(), reason="",
    )

    # 模擬 daily_realized_pnl ≤ -300 → 直接傳給 run_tick 沒辦法,
    # 改用 manual call CircuitBreaker.evaluate_new_entry 來驗證
    cb = CircuitBreaker(Control(db), Positions(db), Events(db))
    reason = cb.evaluate_new_entry(
        symbol="BTC", size_usdt=100.0, universe=universe,
        daily_realized_pnl=-301.0,
    )
    assert reason is not None
    assert Control(db).get_bool("kill_switch", default=False) is True

    # 之後 kill switch 已經被打開 → 即使有正常 fake exchange,signal 還是擋
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    summary = run_tick(db, ex, strategy_name="trend_majors")
    assert summary["triggered"] == 0
    assert summary["blocked"] == 1
