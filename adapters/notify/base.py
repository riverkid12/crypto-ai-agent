"""Notifier abstraction (Protocol + in-memory fake for tests)."""
from dataclasses import dataclass
from typing import Any, Dict, List, Protocol


@dataclass
class Notification:
    type: str                   # e.g. "fill" / "error" / "kill_switch" / "blocked"
    severity: str               # "info" / "warn" / "error"
    payload: Dict[str, Any]


class Notifier(Protocol):
    def send(self, notification: Notification) -> bool:
        """Send a notification. Return True on success, False on failure.

        Implementations must NOT raise on transport errors — return False instead,
        so the tick loop can continue even if Discord/webhook is down.
        """


class FakeNotifier:
    """In-memory notifier for tests. Records all attempts."""

    def __init__(self, fail: bool = False):
        self._fail = fail
        self.sent: List[Notification] = []

    def send(self, notification: Notification) -> bool:
        self.sent.append(notification)
        return not self._fail
