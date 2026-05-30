"""HTTP POST adapter that pushes to chat-notify-hub."""
import json
import requests
from adapters.notify.base import Notification


class ChatNotifyHubNotifier:
    def __init__(self, url: str, timeout: float = 5.0):
        self._url = url
        self._timeout = timeout

    def send(self, notification: Notification) -> bool:
        body = {
            "type": notification.type,
            "severity": notification.severity,
            "payload": notification.payload,
        }
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
