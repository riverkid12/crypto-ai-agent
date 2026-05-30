"""Typed key/value access to the `control` table."""
from datetime import datetime, timezone
from typing import Optional
from db.client import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Control:
    def __init__(self, db: Database):
        self._db = db

    def get(self, key: str) -> Optional[str]:
        row = self._db.query_one("SELECT value FROM control WHERE key = ?", (key,))
        return row[0] if row else None

    def get_bool(self, key: str, default: bool) -> bool:
        v = self.get(key)
        if v is None:
            return default
        return v.strip().lower() in ("true", "1", "yes", "on")

    def get_int(self, key: str, default: int) -> int:
        v = self.get(key)
        if v is None:
            return default
        return int(v)

    def get_float(self, key: str, default: float) -> float:
        v = self.get(key)
        if v is None:
            return default
        return float(v)

    def set(self, key: str, value: str) -> None:
        self._db.execute(
            "INSERT INTO control (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, value, _now()),
        )
