from unittest.mock import MagicMock
from db.repos.positions import Position
from executor.portfolio_snapshot import (
    build_snapshot_md,
    fetch_prices_for_positions,
    fetch_usdt_balance,
    gather_snapshot,
)


def _pos(symbol, qty, avg_entry, current=None, pnl=None):
    return Position(symbol=symbol, qty=qty, avg_entry=avg_entry,
                    current_price=current, unrealized_pnl=pnl,
                    updated_at="2026-05-31T00:00:00+00:00")


def test_build_snapshot_with_balance_and_positions():
    positions = [
        _pos("BTCUSDT", 0.00067, 73938.56),
        _pos("ETHUSDT", 0.0247, 2021.63),
    ]
    prices = {"BTCUSDT": 74000.00, "ETHUSDT": 2025.00}
    md = build_snapshot_md(positions, prices, usdt_balance=9950.46)
    assert "**目前餘額** USDT $9,950.46" in md
    assert "**目前持有**" in md
    assert "BTCUSDT" in md
    assert "ETHUSDT" in md
    # P&L: (74000 - 73938.56) * 0.00067 = ~$0.04
    assert "$+0.04" in md
    # P&L: (2025 - 2021.63) * 0.0247 = ~$0.08
    assert "$+0.08" in md


def test_build_snapshot_without_balance_omits_line():
    """When balance is None, the 目前餘額 line is not emitted."""
    positions = [_pos("BTCUSDT", 0.001, 60000)]
    md = build_snapshot_md(positions, {"BTCUSDT": 60100}, usdt_balance=None)
    assert "目前餘額" not in md
    assert "**目前持有**" in md
    assert "BTCUSDT" in md


def test_build_snapshot_empty_positions():
    md = build_snapshot_md([], {}, usdt_balance=10000.0)
    assert "(無持倉)" in md
    # Still shows balance
    assert "USDT $10,000.00" in md


def test_build_snapshot_missing_price_shows_dash():
    """If a position's symbol has no price in dict, P&L shows '-' (not crash)."""
    positions = [_pos("BTCUSDT", 0.001, 60000)]
    md = build_snapshot_md(positions, prices={}, usdt_balance=None)
    assert "BTCUSDT" in md
    # The P&L column should have "-"
    lines = [l for l in md.split("\n") if "BTCUSDT" in l]
    assert len(lines) == 1
    # Last cell of the row should be "-"
    assert lines[0].rstrip().endswith("- |")


def test_fetch_prices_per_symbol_skips_failures():
    exchange = MagicMock()
    def get_price(symbol):
        if symbol == "BAD":
            raise RuntimeError("nope")
        return 100.0 if symbol == "GOOD1" else 200.0
    exchange.get_price.side_effect = get_price
    prices = fetch_prices_for_positions(exchange, ["GOOD1", "BAD", "GOOD2"])
    assert prices == {"GOOD1": 100.0, "GOOD2": 200.0}


def test_fetch_usdt_balance_extracts_usdt():
    exchange = MagicMock()
    exchange._client.get_account.return_value = {
        "balances": [
            {"asset": "BTC", "free": "1.0", "locked": "0"},
            {"asset": "USDT", "free": "9950.46", "locked": "0"},
            {"asset": "ETH", "free": "100", "locked": "0"},
        ],
    }
    assert fetch_usdt_balance(exchange) == 9950.46


def test_fetch_usdt_balance_returns_none_when_no_client():
    exchange = MagicMock(spec=[])  # no _client attribute
    assert fetch_usdt_balance(exchange) is None


def test_fetch_usdt_balance_returns_none_on_api_error():
    exchange = MagicMock()
    exchange._client.get_account.side_effect = RuntimeError("api down")
    assert fetch_usdt_balance(exchange) is None


def test_gather_snapshot_uses_positions_from_db(db):
    """Integration: positions from real Turso schema + mocked exchange."""
    from db.repos.strategies import Strategies
    from db.repos.positions import Positions
    Strategies(db).insert(name="s1", params={})
    Positions(db).upsert("BTCUSDT", qty=0.001, avg_entry=60000.0)

    exchange = MagicMock()
    exchange.get_price.return_value = 61000.0
    exchange._client.get_account.return_value = {
        "balances": [{"asset": "USDT", "free": "5000", "locked": "0"}],
    }
    md = gather_snapshot(db, exchange)
    assert "**目前餘額** USDT $5,000.00" in md
    assert "BTCUSDT" in md
    # P&L: (61000 - 60000) * 0.001 = $1.00
    assert "$+1.00" in md


def test_gather_snapshot_with_empty_positions(db):
    """gather_snapshot with no positions returns valid string with (無持倉)."""
    exchange = MagicMock()
    exchange.get_price.return_value = 100.0
    exchange._client.get_account.return_value = {"balances": []}  # no USDT
    md = gather_snapshot(db, exchange)
    assert "(無持倉)" in md
