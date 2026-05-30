import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List
from db.client import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Event:
    id: int
    type: str
    payload: dict
    created_at: str


class Events:
    def __init__(self, db: Database):
        self._db = db

    def log(self, type: str, payload: dict) -> int:
        return self._db.execute(
            "INSERT INTO events (type, payload_json, created_at) VALUES (?, ?, ?)",
            (type, json.dumps(payload), _now()),
        )

    def recent(self, limit: int = 50) -> List[Event]:
        rows = self._db.query(
            "SELECT id, type, payload_json, created_at FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [Event(id=r[0], type=r[1], payload=json.loads(r[2]), created_at=r[3])
                for r in rows]

    def count_since(self, type: str, since_iso: str) -> int:
        row = self._db.query_one(
            "SELECT COUNT(*) FROM events WHERE type = ? AND created_at >= ?",
            (type, since_iso),
        )
        return row[0] if row else 0
