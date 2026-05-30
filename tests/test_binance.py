from unittest.mock import MagicMock, patch
import pytest
from adapters.exchanges.binance import BinanceExchange
from adapters.exchanges.base import ExchangeOrder


@patch("adapters.exchanges.binance.Client")
def test_get_price_uses_get_symbol_ticker(MockClient):
    mock_client = MagicMock()
    mock_client.get_symbol_ticker.return_value = {"symbol": "BTCUSDT", "price": "60000.5"}
    MockClient.return_value = mock_client

    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    price = ex.get_price("BTCUSDT")

    MockClient.assert_called_once_with("k", "s", testnet=True)
    mock_client.get_symbol_ticker.assert_called_once_with(symbol="BTCUSDT")
    assert price == 60000.5


@patch("adapters.exchanges.binance.Client")
def test_get_price_propagates_unknown_symbol(MockClient):
    from binance.exceptions import BinanceAPIException
    mock_client = MagicMock()
    mock_client.get_symbol_ticker.side_effect = BinanceAPIException(
        MagicMock(status_code=400), 400, '{"code":-1121,"msg":"Invalid symbol."}'
    )
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    with pytest.raises(BinanceAPIException):
        ex.get_price("UNKNOWN")


@patch("adapters.exchanges.binance.Client")
def test_place_market_buy_returns_exchange_order(MockClient):
    mock_client = MagicMock()
    mock_client.create_order.return_value = {
        "symbol": "BTCUSDT", "orderId": 12345, "status": "FILLED",
        "executedQty": "0.001", "cummulativeQuoteQty": "60.0",
        "fills": [
            {"price": "60000.0", "qty": "0.001", "commission": "0.06", "commissionAsset": "USDT"},
        ],
    }
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)

    order = ex.place_order("BTCUSDT", "buy", qty=0.001, type="market")

    mock_client.create_order.assert_called_once_with(
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
    mock_client = MagicMock()
    mock_client.create_order.return_value = {
        "symbol": "BTCUSDT", "orderId": 99, "status": "FILLED",
        "executedQty": "0.001",
        "fills": [{"price": "60000.0", "qty": "0.001", "commission": "0.06", "commissionAsset": "USDT"}],
    }
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    order = ex.place_order("BTCUSDT", "sell", qty=0.001, type="market")
    mock_client.create_order.assert_called_once_with(
        symbol="BTCUSDT", side="SELL", type="MARKET", quantity=0.001,
    )
    assert order.status == "filled"


@patch("adapters.exchanges.binance.Client")
def test_place_order_partial_fill(MockClient):
    mock_client = MagicMock()
    mock_client.create_order.return_value = {
        "symbol": "BTCUSDT", "orderId": 5, "status": "PARTIALLY_FILLED",
        "executedQty": "0.0005",
        "fills": [{"price": "60000.0", "qty": "0.0005", "commission": "0.03", "commissionAsset": "USDT"}],
    }
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    order = ex.place_order("BTCUSDT", "buy", qty=0.001, type="market")
    assert order.status == "partial"
    assert order.fill_qty == 0.0005


@patch("adapters.exchanges.binance.Client")
def test_cancel_returns_true_on_success(MockClient):
    mock_client = MagicMock()
    mock_client.cancel_order.return_value = {"orderId": 12345, "status": "CANCELED"}
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    ok = ex.cancel("12345", symbol="BTCUSDT")
    assert ok is True


@patch("adapters.exchanges.binance.Client")
def test_cancel_returns_false_on_error(MockClient):
    from binance.exceptions import BinanceAPIException
    mock_client = MagicMock()
    mock_client.cancel_order.side_effect = BinanceAPIException(
        MagicMock(status_code=400), 400, '{"code":-2011,"msg":"Unknown order."}'
    )
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    ok = ex.cancel("99999", symbol="BTCUSDT")
    assert ok is False


@patch("adapters.exchanges.binance.Client")
def test_fee_extracted_only_when_quote_is_usdt(MockClient):
    """If commission asset isn't USDT (e.g., BNB discount), fee_usdt=0 in P1."""
    mock_client = MagicMock()
    mock_client.create_order.return_value = {
        "symbol": "BTCUSDT", "orderId": 1, "status": "FILLED",
        "executedQty": "0.001",
        "fills": [{"price": "60000.0", "qty": "0.001", "commission": "0.0001", "commissionAsset": "BNB"}],
    }
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    order = ex.place_order("BTCUSDT", "buy", qty=0.001, type="market")
    assert order.fee_usdt == 0  # BNB fee not converted in P1; P2 can fix
