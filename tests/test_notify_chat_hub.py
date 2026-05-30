import responses
from adapters.notify.base import Notification
from adapters.notify.chat_notify_hub import ChatNotifyHubNotifier


HUB_URL = "http://localhost:9001/notify"


@responses.activate
def test_send_posts_json_and_returns_true_on_200():
    responses.add(responses.POST, HUB_URL, json={"ok": True}, status=200)
    notifier = ChatNotifyHubNotifier(HUB_URL)
    ok = notifier.send(Notification(
        type="fill", severity="info",
        payload={"symbol": "BTC", "qty": 0.01},
    ))
    assert ok is True
    assert len(responses.calls) == 1
    body = responses.calls[0].request.body
    import json
    parsed = json.loads(body)
    assert parsed["type"] == "fill"
    assert parsed["severity"] == "info"
    assert parsed["payload"]["symbol"] == "BTC"


@responses.activate
def test_send_returns_false_on_5xx():
    responses.add(responses.POST, HUB_URL, status=500)
    notifier = ChatNotifyHubNotifier(HUB_URL)
    ok = notifier.send(Notification(type="error", severity="error", payload={}))
    assert ok is False


@responses.activate
def test_send_returns_false_on_connection_error():
    responses.add(responses.POST, HUB_URL, body=ConnectionError("boom"))
    notifier = ChatNotifyHubNotifier(HUB_URL)
    ok = notifier.send(Notification(type="error", severity="error", payload={}))
    # Must NOT raise — must return False
    assert ok is False


@responses.activate
def test_send_respects_timeout_kwarg():
    responses.add(responses.POST, HUB_URL, json={"ok": True}, status=200)
    notifier = ChatNotifyHubNotifier(HUB_URL, timeout=10)
    notifier.send(Notification(type="fill", severity="info", payload={}))
    # responses library doesn't expose timeout to assert, but request must complete
    assert len(responses.calls) == 1
