from db.repos.signals import Signal
from executor.matcher import should_trigger


def _signal(side="long", entry=None):
    return Signal(
        id=1, strategy_id=1, symbol="BTC", side=side,
        entry_price=entry, stop_price=None, target_price=None,
        size_usdt=500.0, status="pending", reason="",
        expires_at=None, created_at="2026-05-30T00:00:00+00:00",
    )


def test_market_long_always_triggers():
    sig = _signal(side="long", entry=None)
    assert should_trigger(sig, current_price=60000.0) is True


def test_long_above_entry_triggers():
    sig = _signal(side="long", entry=60000.0)
    assert should_trigger(sig, current_price=60001.0) is True


def test_long_at_entry_triggers():
    sig = _signal(side="long", entry=60000.0)
    assert should_trigger(sig, current_price=60000.0) is True


def test_long_below_entry_does_not_trigger():
    sig = _signal(side="long", entry=60000.0)
    assert should_trigger(sig, current_price=59999.0) is False


def test_flat_signal_triggers_when_holding():
    sig = _signal(side="flat", entry=None)
    assert should_trigger(sig, current_price=60000.0, holding_qty=0.01) is True


def test_flat_signal_does_not_trigger_when_no_holding():
    sig = _signal(side="flat", entry=None)
    assert should_trigger(sig, current_price=60000.0, holding_qty=0.0) is False
