"""Binance adapter (testnet & live, spot-only for P1)."""
from typing import Optional
from binance.client import Client
from binance.exceptions import BinanceAPIException
from adapters.exchanges.base import ExchangeOrder


# Binance order status -> our normalized status
_STATUS_MAP = {
    "NEW": "new",
    "PARTIALLY_FILLED": "partial",
    "FILLED": "filled",
    "CANCELED": "cancelled",
    "EXPIRED": "cancelled",
    "REJECTED": "failed",
}


class BinanceExchange:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self._client = Client(api_key, api_secret, testnet=testnet)

    def get_price(self, symbol: str) -> float:
        ticker = self._client.get_symbol_ticker(symbol=symbol)
        return float(ticker["price"])

    def place_order(self, symbol: str, side: str, qty: float,
                    price: Optional[float] = None, type: str = "market") -> ExchangeOrder:
        if type != "market":
            raise NotImplementedError("P1 only supports market orders")
        order = self._client.create_order(
            symbol=symbol,
            side=side.upper(),
            type="MARKET",
            quantity=qty,
        )
        return _order_dict_to_exchange_order(order)

    def cancel(self, exchange_order_id: str, symbol: Optional[str] = None) -> bool:
        if symbol is None:
            # Binance requires symbol for cancel; our Protocol allows id-only,
            # but in practice the caller (tick.py) has the symbol available.
            return False
        try:
            self._client.cancel_order(symbol=symbol, orderId=int(exchange_order_id))
            return True
        except BinanceAPIException:
            return False


def _order_dict_to_exchange_order(order: dict) -> ExchangeOrder:
    """Convert Binance create_order response dict to our ExchangeOrder."""
    status = _STATUS_MAP.get(order.get("status", ""), "failed")
    executed_qty = float(order.get("executedQty", 0) or 0)

    # Weighted-average fill price from `fills` array
    fills = order.get("fills", [])
    if fills and executed_qty > 0:
        total_quote = sum(float(f["price"]) * float(f["qty"]) for f in fills)
        fill_price = total_quote / executed_qty
    else:
        fill_price = None

    # Fee: only count USDT-denominated commissions in P1
    fee_usdt = sum(
        float(f.get("commission", 0))
        for f in fills
        if f.get("commissionAsset") == "USDT"
    )

    return ExchangeOrder(
        id=str(order.get("orderId", "")),
        status=status,
        fill_qty=executed_qty,
        fill_price=fill_price,
        fee_usdt=fee_usdt,
    )
