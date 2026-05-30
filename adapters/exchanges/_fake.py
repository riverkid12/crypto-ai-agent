import itertools
from typing import Dict, Optional
from adapters.exchanges.base import ExchangeOrder


class FakeExchange:
    """In-memory exchange for tests / dev runs.

    Usage:
        ex = FakeExchange()
        ex.set_price("BTC", 60000.0)
        order = ex.place_order("BTC", "buy", qty=0.01)
    """

    DEFAULT_FEE_RATE = 0.001  # 0.1%

    def __init__(self, fee_rate: float = DEFAULT_FEE_RATE):
        self._prices: Dict[str, float] = {}
        self._fee_rate = fee_rate
        self._id_seq = itertools.count(1)
        self._fail_remaining = 0

    # --- test hooks ---
    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price

    def fail_next_n_orders(self, n: int) -> None:
        self._fail_remaining = n

    # --- Exchange protocol ---
    def get_price(self, symbol: str) -> float:
        if symbol not in self._prices:
            raise KeyError(f"unknown symbol: {symbol}")
        return self._prices[symbol]

    def place_order(self, symbol: str, side: str, qty: float,
                    price: Optional[float] = None, type: str = "market") -> ExchangeOrder:
        oid = f"fake-{next(self._id_seq)}"
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            return ExchangeOrder(id=oid, status="failed", fill_qty=0.0,
                                 fill_price=None, fee_usdt=0.0)
        fill_price = self.get_price(symbol) if type == "market" else (price or 0.0)
        fee = abs(qty * fill_price * self._fee_rate)
        return ExchangeOrder(id=oid, status="filled", fill_qty=qty,
                             fill_price=fill_price, fee_usdt=fee)

    def cancel(self, exchange_order_id: str) -> bool:
        # P0 fake: all market orders fill immediately, no open orders to cancel
        return False
