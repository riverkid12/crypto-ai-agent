from unittest.mock import MagicMock, patch
import pytest
from adapters.exchanges.binance import BinanceExchange
from adapters.exchanges.base import ExchangeOrder


def _btc_lot_size():
    """Standard BTCUSDT LOT_SIZE filter response (step 0.00001, min 0.0001)."""
    return {
        "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "0.00001", "minQty": "0.0001"},
        ],
    }


def _make_client(create_order_return=None, ticker_return=None, lot_size=None,
                 create_order_side_effect=None, cancel_return=None,
                 cancel_side_effect=None):
    """Build a configured mock client."""
    m = MagicMock()
    if ticker_return is not None:
        m.get_symbol_ticker.return_value = ticker_return
    m.get_symbol_info.return_value = lot_size or _btc_lot_size()
    if create_order_return is not None:
        m.create_order.return_value = create_order_return
    if create_order_side_effect is not None:
        m.create_order.side_effect = create_order_side_effect
    if cancel_return is not None:
        m.cancel_order.return_value = cancel_return
    if cancel_side_effect is not None:
        m.cancel_order.side_effect = cancel_side_effect
    return m


@patch("adapters.exchanges.binance.Client")
def test_get_price_uses_get_symbol_ticker(MockClient):
    MockClient.return_value = _make_client(
        ticker_return={"symbol": "BTCUSDT", "price": "60000.5"})

    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    price = ex.get_price("BTCUSDT")

    MockClient.assert_called_once_with("k", "s", testnet=True)
    assert price == 60000.5


@patch("adapters.exchanges.binance.Client")
def test_get_price_propagates_unknown_symbol(MockClient):
    from binance.exceptions import BinanceAPIException
    m = _make_client()
    m.get_symbol_ticker.side_effect = BinanceAPIException(
        MagicMock(status_code=400), 400, '{"code":-1121,"msg":"Invalid symbol."}'
    )
    MockClient.return_value = m
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    with pytest.raises(BinanceAPIException):
        ex.get_price("UNKNOWN")


@patch("adapters.exchanges.binance.Client")
def test_place_market_buy_returns_exchange_order(MockClient):
    MockClient.return_value = _make_client(create_order_return={
        "symbol": "BTCUSDT", "orderId": 12345, "status": "FILLED",
        "executedQty": "0.001", "cummulativeQuoteQty": "60.0",
        "fills": [
            {"price": "60000.0", "qty": "0.001", "commission": "0.06", "commissionAsset": "USDT"},
        ],
    })
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)

    order = ex.place_order("BTCUSDT", "buy", qty=0.001, type="market")

    # qty 0.001 with step 0.00001 -> 0.001 (no change)
    MockClient.return_value.create_order.assert_called_once_with(
        symbol="BTCUSDT", side="BUY", type="MARKET", quantity=0.001,
    )
    assert isinstance(order, ExchangeOrder)
    assert order.id == "12345"
    assert order.status == "filled"
    assert order.fill_qty == 0.001
    assert order.fill_price == 60000.0
    assert order.fee_usdt == 0.06


@patch("adapters.exchanges.binance.Client")
def test_place_market_sell(MockClient):
    MockClient.return_value = _make_client(create_order_return={
        "symbol": "BTCUSDT", "orderId": 99, "status": "FILLED",
        "executedQty": "0.001",
        "fills": [{"price": "60000.0", "qty": "0.001", "commission": "0.06", "commissionAsset": "USDT"}],
    })
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    order = ex.place_order("BTCUSDT", "sell", qty=0.001, type="market")
    MockClient.return_value.create_order.assert_called_once_with(
        symbol="BTCUSDT", side="SELL", type="MARKET", quantity=0.001,
    )
    assert order.status == "filled"


@patch("adapters.exchanges.binance.Client")
def test_place_order_partial_fill(MockClient):
    MockClient.return_value = _make_client(create_order_return={
        "symbol": "BTCUSDT", "orderId": 5, "status": "PARTIALLY_FILLED",
        "executedQty": "0.0005",
        "fills": [{"price": "60000.0", "qty": "0.0005", "commission": "0.03", "commissionAsset": "USDT"}],
    })
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    order = ex.place_order("BTCUSDT", "buy", qty=0.001, type="market")
    assert order.status == "partial"
    assert order.fill_qty == 0.0005


@patch("adapters.exchanges.binance.Client")
def test_cancel_returns_true_on_success(MockClient):
    MockClient.return_value = _make_client(cancel_return={"orderId": 12345, "status": "CANCELED"})
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    ok = ex.cancel("12345", symbol="BTCUSDT")
    assert ok is True


@patch("adapters.exchanges.binance.Client")
def test_cancel_returns_false_on_error(MockClient):
    from binance.exceptions import BinanceAPIException
    MockClient.return_value = _make_client(cancel_side_effect=BinanceAPIException(
        MagicMock(status_code=400), 400, '{"code":-2011,"msg":"Unknown order."}'
    ))
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    ok = ex.cancel("99999", symbol="BTCUSDT")
    assert ok is False


@patch("adapters.exchanges.binance.Client")
def test_fee_extracted_only_when_quote_is_usdt(MockClient):
    """If commission asset isn't USDT (e.g., BNB discount), fee_usdt=0 in P1."""
    MockClient.return_value = _make_client(create_order_return={
        "symbol": "BTCUSDT", "orderId": 1, "status": "FILLED",
        "executedQty": "0.001",
        "fills": [{"price": "60000.0", "qty": "0.001", "commission": "0.0001", "commissionAsset": "BNB"}],
    })
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    order = ex.place_order("BTCUSDT", "buy", qty=0.001, type="market")
    assert order.fee_usdt == 0  # BNB fee not converted in P1; P2 can fix


# --- new LOT_SIZE rounding tests ---

@patch("adapters.exchanges.binance.Client")
def test_qty_rounded_down_to_lot_step(MockClient):
    """qty=0.001234567 with step 0.00001 -> 0.00123 (truncated, not rounded)."""
    MockClient.return_value = _make_client(create_order_return={
        "symbol": "BTCUSDT", "orderId": 7, "status": "FILLED",
        "executedQty": "0.00123",
        "fills": [{"price": "60000.0", "qty": "0.00123", "commission": "0.07", "commissionAsset": "USDT"}],
    })
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    ex.place_order("BTCUSDT", "buy", qty=0.001234567, type="market")
    MockClient.return_value.create_order.assert_called_once_with(
        symbol="BTCUSDT", side="BUY", type="MARKET", quantity=0.00123,
    )


@patch("adapters.exchanges.binance.Client")
def test_qty_below_min_returns_failed_without_calling_create_order(MockClient):
    """qty=0.00001 with min_qty 0.0001 -> too small, no order placed."""
    MockClient.return_value = _make_client()
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    order = ex.place_order("BTCUSDT", "buy", qty=0.00001, type="market")
    assert order.status == "failed"
    assert order.fill_qty == 0.0
    MockClient.return_value.create_order.assert_not_called()


@patch("adapters.exchanges.binance.Client")
def test_lot_size_cached_per_symbol(MockClient):
    """get_symbol_info should only be called once per symbol."""
    MockClient.return_value = _make_client(create_order_return={
        "symbol": "BTCUSDT", "orderId": 1, "status": "FILLED",
        "executedQty": "0.001",
        "fills": [{"price": "60000.0", "qty": "0.001", "commission": "0.06", "commissionAsset": "USDT"}],
    })
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    ex.place_order("BTCUSDT", "buy", qty=0.001, type="market")
    ex.place_order("BTCUSDT", "buy", qty=0.001, type="market")
    assert MockClient.return_value.get_symbol_info.call_count == 1


@patch("adapters.exchanges.binance.Client")
def test_sol_step_size_3_decimals(MockClient):
    """SOLUSDT typically has stepSize=0.001 (3 decimals)."""
    MockClient.return_value = _make_client(
        lot_size={"filters": [{"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.01"}]},
        create_order_return={
            "symbol": "SOLUSDT", "orderId": 1, "status": "FILLED",
            "executedQty": "0.333",
            "fills": [{"price": "150.0", "qty": "0.333", "commission": "0.05", "commissionAsset": "USDT"}],
        },
    )
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    ex.place_order("SOLUSDT", "buy", qty=0.33345, type="market")
    MockClient.return_value.create_order.assert_called_once_with(
        symbol="SOLUSDT", side="BUY", type="MARKET", quantity=0.333,
    )
