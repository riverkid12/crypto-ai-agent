from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from db.client import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Position:
    symbol: str
    qty: float
    avg_entry: float
    current_price: Optional[float]
    unrealized_pnl: Optional[float]
    updated_at: str


_COLS = "symbol, qty, avg_entry, current_price, unrealized_pnl, updated_at"


def _row_to_position(r) -> Position:
    return Position(
        symbol=r[0], qty=r[1], avg_entry=r[2],
        current_price=r[3], unrealized_pnl=r[4], updated_at=r[5],
    )


class Positions:
    def __init__(self, db: Database):
        self._db = db

    def upsert(self, symbol: str, qty: float, avg_entry: float,
               current_price: Optional[float] = None) -> None:
        unrealized = None
        if current_price is not None:
            unrealized = (current_price - avg_entry) * qty
        self._db.execute(
            "INSERT INTO positions (symbol, qty, avg_entry, current_price, unrealized_pnl, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(symbol) DO UPDATE SET qty = excluded.qty, "
            "avg_entry = excluded.avg_entry, current_price = excluded.current_price, "
            "unrealized_pnl = excluded.unrealized_pnl, updated_at = excluded.updated_at",
            (symbol, qty, avg_entry, current_price, unrealized, _now()),
        )

    def get(self, symbol: str) -> Optional[Position]:
        row = self._db.query_one(f"SELECT {_COLS} FROM positions WHERE symbol = ?", (symbol,))
        return _row_to_position(row) if row else None

    def list_all(self) -> List[Position]:
        rows = self._db.query(f"SELECT {_COLS} FROM positions ORDER BY symbol")
        return [_row_to_position(r) for r in rows]

    def count_open(self) -> int:
        row = self._db.query_one("SELECT COUNT(*) FROM positions WHERE qty != 0")
        return row[0] if row else 0

    def get_qty(self, symbol: str) -> float:
        pos = self.get(symbol)
        return pos.qty if pos else 0.0

    def delete(self, symbol: str) -> None:
        self._db.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
