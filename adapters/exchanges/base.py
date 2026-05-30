from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class ExchangeOrder:
    id: str                   # exchange order id
    status: str               # new / partial / filled / cancelled / failed
    fill_qty: float
    fill_price: Optional[float]
    fee_usdt: float


class Exchange(Protocol):
    """Abstract trading interface.

    P0 only uses _fake.py implementation; P1 adds binance.py.
    """

    def get_price(self, symbol: str) -> float:
        """Return latest mid price for symbol. Raises on unknown symbol."""

    def place_order(self, symbol: str, side: str, qty: float,
                    price: Optional[float] = None, type: str = "market") -> ExchangeOrder:
        """Place an order.

        side: 'buy' or 'sell'
        type: 'market' or 'limit' (P0 only uses market)
        Returns: ExchangeOrder with exchange-assigned id and current status.
        """

    def cancel(self, exchange_order_id: str) -> bool:
        """Cancel an open order. Returns True on success, False if not found / already filled."""
