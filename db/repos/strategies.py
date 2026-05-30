"""Strategy registry."""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from db.client import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Strategy:
    id: int
    name: str
    params: dict
    active: bool
    updated_at: str


class Strategies:
    def __init__(self, db: Database):
        self._db = db

    def insert(self, name: str, params: dict, active: bool = True) -> int:
        return self._db.execute(
            "INSERT INTO strategies (name, params_json, active, updated_at) VALUES (?, ?, ?, ?)",
            (name, json.dumps(params), 1 if active else 0, _now()),
        )

    def get_by_name(self, name: str) -> Optional[Strategy]:
        row = self._db.query_one(
            "SELECT id, name, params_json, active, updated_at FROM strategies WHERE name = ?",
            (name,),
        )
        if not row:
            return None
        return Strategy(
            id=row[0],
            name=row[1],
            params=json.loads(row[2]),
            active=bool(row[3]),
            updated_at=row[4],
        )

    def list_active(self) -> List[Strategy]:
        rows = self._db.query(
            "SELECT id, name, params_json, active, updated_at FROM strategies "
            "WHERE active = 1 ORDER BY id"
        )
        return [
            Strategy(
                id=r[0], name=r[1], params=json.loads(r[2]),
                active=bool(r[3]), updated_at=r[4],
            )
            for r in rows
        ]

    def set_active(self, name: str, active: bool) -> None:
        self._db.execute(
            "UPDATE strategies SET active = ?, updated_at = ? WHERE name = ?",
            (1 if active else 0, _now(), name),
        )
