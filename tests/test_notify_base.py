from adapters.notify.base import FakeNotifier, Notification


def test_fake_notifier_records_messages():
    n = FakeNotifier()
    n.send(Notification(type="fill", severity="info", payload={"symbol": "BTC", "qty": 0.01}))
    assert len(n.sent) == 1
    assert n.sent[0].type == "fill"
    assert n.sent[0].severity == "info"
    assert n.sent[0].payload["symbol"] == "BTC"


def test_fake_notifier_records_multiple_messages():
    n = FakeNotifier()
    n.send(Notification(type="fill", severity="info", payload={"symbol": "BTC"}))
    n.send(Notification(type="error", severity="error", payload={"err": "timeout"}))
    types = [m.type for m in n.sent]
    assert types == ["fill", "error"]


def test_fake_notifier_can_simulate_failure():
    n = FakeNotifier(fail=True)
    # send returns False on failure, doesn't raise
    ok = n.send(Notification(type="fill", severity="info", payload={}))
    assert ok is False
    # message still recorded in attempts
    assert len(n.sent) == 1


def test_fake_notifier_success_default():
    n = FakeNotifier()
    ok = n.send(Notification(type="fill", severity="info", payload={}))
    assert ok is True
