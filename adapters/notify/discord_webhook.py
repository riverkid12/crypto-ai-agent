"""Discord webhook adapter — posts Notification as a Discord embed.

Discord webhook URLs look like:
    https://discord.com/api/webhooks/<id>/<token>
"""
import json
from datetime import datetime, timezone
import requests
from adapters.notify.base import Notification


# Discord embed color codes by severity
_SEVERITY_COLOR = {
    "info": 0x57F287,   # green
    "warn": 0xFEE75C,   # yellow
    "error": 0xED4245,  # red
}
_DEFAULT_COLOR = 0x99AAB5  # neutral gray

# Discord limits
_MAX_FIELD_VALUE_LEN = 1024
_MAX_FIELDS = 25


class DiscordWebhookNotifier:
    def __init__(self, url: str, timeout: float = 5.0):
        self._url = url
        self._timeout = timeout

    def send(self, notification: Notification) -> bool:
        fields = []
        for k, v in list(notification.payload.items())[:_MAX_FIELDS]:
            value_str = str(v)
            if len(value_str) > _MAX_FIELD_VALUE_LEN:
                value_str = value_str[:_MAX_FIELD_VALUE_LEN - 3] + "..."
            fields.append({"name": str(k), "value": value_str, "inline": True})

        embed = {
            "title": f"[{notification.severity.upper()}] {notification.type}",
            "color": _SEVERITY_COLOR.get(notification.severity, _DEFAULT_COLOR),
            "fields": fields,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        body = {"embeds": [embed]}
        try:
            resp = requests.post(
                self._url,
                data=json.dumps(body),
                headers={"Content-Type": "application/json"},
                timeout=self._timeout,
            )
            return 200 <= resp.status_code < 300
        except requests.exceptions.RequestException:
            return False
        except ConnectionError:
            return False
