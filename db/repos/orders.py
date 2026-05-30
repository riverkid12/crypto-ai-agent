from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from db.client import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Order:
    id: int
    signal_id: Optional[int]
    exchange_order_id: Optional[str]
    symbol: str
    side: str
    qty: float
    price: Optional[float]
    type: str
    status: str
    fill_qty: float
    fill_price: Optional[float]
    fee_usdt: float
    created_at: str
    filled_at: Optional[str]


_COLS = "id, signal_id, exchange_order_id, symbol, side, qty, price, type, status, fill_qty, fill_price, fee_usdt, created_at, filled_at"


def _row_to_order(r) -> Order:
    return Order(
        id=r[0], signal_id=r[1], exchange_order_id=r[2], symbol=r[3],
        side=r[4], qty=r[5], price=r[6], type=r[7], status=r[8],
        fill_qty=r[9] or 0.0, fill_price=r[10], fee_usdt=r[11] or 0.0,
        created_at=r[12], filled_at=r[13],
    )


class Orders:
    def __init__(self, db: Database):
        self._db = db

    def insert(self, *, signal_id, exchange_order_id, symbol, side, qty, price, type, status) -> int:
        return self._db.execute(
            "INSERT INTO orders (signal_id, exchange_order_id, symbol, side, qty, price, type, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (signal_id, exchange_order_id, symbol, side, qty, price, type, status, _now()),
        )

    def get(self, order_id: int) -> Optional[Order]:
        row = self._db.query_one(f"SELECT {_COLS} FROM orders WHERE id = ?", (order_id,))
        return _row_to_order(row) if row else None

    def update_fill(self, order_id: int, *, fill_qty, fill_price, fee_usdt, status) -> None:
        self._db.execute(
            "UPDATE orders SET fill_qty = ?, fill_price = ?, fee_usdt = ?, status = ?, filled_at = ? WHERE id = ?",
            (fill_qty, fill_price, fee_usdt, status, _now(), order_id),
        )
