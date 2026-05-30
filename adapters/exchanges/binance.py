"""Binance adapter (testnet & live, spot-only for P1)."""
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Optional, Tuple
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
        self._lot_size_cache: Dict[str, Tuple[Decimal, Decimal]] = {}

    def get_price(self, symbol: str) -> float:
        ticker = self._client.get_symbol_ticker(symbol=symbol)
        return float(ticker["price"])

    def _get_lot_size(self, symbol: str) -> Tuple[Decimal, Decimal]:
        """Return (step_size, min_qty) for symbol from LOT_SIZE filter."""
        if symbol not in self._lot_size_cache:
            info = self._client.get_symbol_info(symbol)
            step = Decimal("0.00001")
            min_qty = Decimal("0")
            for f in info.get("filters", []):
                if f.get("filterType") == "LOT_SIZE":
                    step = Decimal(str(f["stepSize"]))
                    min_qty = Decimal(str(f["minQty"]))
                    break
            self._lot_size_cache[symbol] = (step, min_qty)
        return self._lot_size_cache[symbol]

    def _round_qty(self, symbol: str, qty: float) -> float:
        """Round qty DOWN to symbol's LOT_SIZE step. Returns 0.0 if below min_qty."""
        step, min_qty = self._get_lot_size(symbol)
        qty_d = Decimal(str(qty))
        # Truncate to nearest step
        rounded = (qty_d / step).to_integral_value(rounding=ROUND_DOWN) * step
        if rounded < min_qty:
            return 0.0
        return float(rounded)

    def place_order(self, symbol: str, side: str, qty: float,
                    price: Optional[float] = None, type: str = "market") -> ExchangeOrder:
        if type != "market":
            raise NotImplementedError("P1 only supports market orders")
        rounded_qty = self._round_qty(symbol, qty)
        if rounded_qty <= 0:
            return ExchangeOrder(id="", status="failed", fill_qty=0.0,
                                 fill_price=None, fee_usdt=0.0)
        order = self._client.create_order(
            symbol=symbol,
            side=side.upper(),
            type="MARKET",
            quantity=rounded_qty,
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
