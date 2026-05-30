import json
import responses
from adapters.notify.base import Notification
from adapters.notify.discord_webhook import DiscordWebhookNotifier


WEBHOOK = "https://discord.com/api/webhooks/123/abc"


@responses.activate
def test_send_posts_embed_format_and_returns_true_on_204():
    responses.add(responses.POST, WEBHOOK, status=204)
    notifier = DiscordWebhookNotifier(WEBHOOK)
    ok = notifier.send(Notification(
        type="fill", severity="info",
        payload={"symbol": "BTCUSDT", "qty": 0.001, "price": 60000},
    ))
    assert ok is True
    assert len(responses.calls) == 1
    body = json.loads(responses.calls[0].request.body)
    assert "embeds" in body
    embed = body["embeds"][0]
    assert "[INFO]" in embed["title"]
    assert "fill" in embed["title"]
    assert embed["color"] == 0x57F287
    # All payload keys present as fields
    names = {f["name"] for f in embed["fields"]}
    assert names == {"symbol", "qty", "price"}


@responses.activate
def test_severity_colors():
    """info=green, warn=yellow, error=red."""
    for severity, expected_color in [
        ("info", 0x57F287),
        ("warn", 0xFEE75C),
        ("error", 0xED4245),
    ]:
        responses.add(responses.POST, WEBHOOK, status=204)
    notifier = DiscordWebhookNotifier(WEBHOOK)
    for severity, expected_color in [
        ("info", 0x57F287),
        ("warn", 0xFEE75C),
        ("error", 0xED4245),
    ]:
        notifier.send(Notification(type="t", severity=severity, payload={}))
    for call, expected_color in zip(responses.calls, [0x57F287, 0xFEE75C, 0xED4245]):
        body = json.loads(call.request.body)
        assert body["embeds"][0]["color"] == expected_color


@responses.activate
def test_send_returns_false_on_4xx():
    responses.add(responses.POST, WEBHOOK, status=400, json={"message": "Invalid webhook"})
    notifier = DiscordWebhookNotifier(WEBHOOK)
    ok = notifier.send(Notification(type="fill", severity="info", payload={}))
    assert ok is False


@responses.activate
def test_send_returns_false_on_connection_error():
    responses.add(responses.POST, WEBHOOK, body=ConnectionError("boom"))
    notifier = DiscordWebhookNotifier(WEBHOOK)
    ok = notifier.send(Notification(type="error", severity="error", payload={}))
    assert ok is False  # must NOT raise


@responses.activate
def test_send_truncates_long_field_values():
    """Discord field value max is 1024 chars."""
    responses.add(responses.POST, WEBHOOK, status=204)
    notifier = DiscordWebhookNotifier(WEBHOOK)
    notifier.send(Notification(
        type="error", severity="error",
        payload={"err": "x" * 2000},
    ))
    body = json.loads(responses.calls[0].request.body)
    field = body["embeds"][0]["fields"][0]
    assert len(field["value"]) <= 1024


@responses.activate
def test_send_caps_fields_at_25():
    """Discord max 25 fields per embed."""
    responses.add(responses.POST, WEBHOOK, status=204)
    notifier = DiscordWebhookNotifier(WEBHOOK)
    payload = {f"k{i}": i for i in range(30)}
    notifier.send(Notification(type="x", severity="info", payload=payload))
    body = json.loads(responses.calls[0].request.body)
    assert len(body["embeds"][0]["fields"]) <= 25


@responses.activate
def test_unknown_severity_falls_back_to_neutral():
    """Unknown severity uses gray color, doesn't crash."""
    responses.add(responses.POST, WEBHOOK, status=204)
    notifier = DiscordWebhookNotifier(WEBHOOK)
    ok = notifier.send(Notification(type="t", severity="totally_unknown", payload={}))
    assert ok is True
