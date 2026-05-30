"""Signal CRUD."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from db.client import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Signal:
    id: int
    strategy_id: int
    symbol: str
    side: str
    entry_price: Optional[float]
    stop_price: Optional[float]
    target_price: Optional[float]
    size_usdt: float
    status: str
    reason: Optional[str]
    expires_at: Optional[str]
    created_at: str


def _row_to_signal(r) -> Signal:
    return Signal(
        id=r[0], strategy_id=r[1], symbol=r[2], side=r[3],
        entry_price=r[4], stop_price=r[5], target_price=r[6],
        size_usdt=r[7], status=r[8], reason=r[9],
        expires_at=r[10], created_at=r[11],
    )


_COLS = "id, strategy_id, symbol, side, entry_price, stop_price, target_price, size_usdt, status, reason, expires_at, created_at"


class Signals:
    def __init__(self, db: Database):
        self._db = db

    def insert(self, *, strategy_id: int, symbol: str, side: str,
               entry_price: Optional[float], stop_price: Optional[float],
               target_price: Optional[float], size_usdt: float,
               expires_at: Optional[str], reason: Optional[str]) -> int:
        return self._db.execute(
            "INSERT INTO signals (strategy_id, symbol, side, entry_price, stop_price, "
            "target_price, size_usdt, status, reason, expires_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
            (strategy_id, symbol, side, entry_price, stop_price,
             target_price, size_usdt, reason, expires_at, _now()),
        )

    def get(self, signal_id: int) -> Optional[Signal]:
        row = self._db.query_one(
            f"SELECT {_COLS} FROM signals WHERE id = ?", (signal_id,))
        return _row_to_signal(row) if row else None

    def list_active(self) -> List[Signal]:
        rows = self._db.query(
            f"SELECT {_COLS} FROM signals "
            "WHERE status = 'pending' AND (expires_at IS NULL OR expires_at > ?)",
            (_now(),),
        )
        return [_row_to_signal(r) for r in rows]

    def mark_triggered(self, signal_id: int) -> None:
        self._db.execute(
            "UPDATE signals SET status = 'triggered' WHERE id = ?",
            (signal_id,),
        )

    def mark_status(self, signal_id: int, status: str) -> None:
        self._db.execute(
            "UPDATE signals SET status = ? WHERE id = ?",
            (status, signal_id),
        )
