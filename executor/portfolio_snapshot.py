"""Build a markdown snapshot of current portfolio for inclusion in notifications."""
from typing import Dict, List, Optional
from db.client import Database
from db.repos.positions import Position, Positions

# Event types that get portfolio snapshot attached
PORTFOLIO_EVENT_TYPES = {"fill", "blocked", "kill_switch", "circuit_open"}


def fetch_prices_for_positions(exchange, symbols: List[str]) -> Dict[str, float]:
    """Fetch current prices via exchange.get_price() per symbol.

    Returns dict {symbol: price}. Missing symbol on error (swallow per-symbol).
    """
    prices: Dict[str, float] = {}
    for s in symbols:
        try:
            prices[s] = exchange.get_price(s)
        except Exception:
            pass
    return prices


def fetch_usdt_balance(exchange) -> Optional[float]:
    """Get USDT free balance from a Binance-style exchange. None if unavailable.

    Accesses exchange._client.get_account() — works for BinanceExchange. Other
    exchange adapters that don't expose ._client will return None gracefully.
    """
    client = getattr(exchange, "_client", None)
    if client is None:
        return None
    try:
        acct = client.get_account()
        for b in acct.get("balances", []):
            if b.get("asset") == "USDT":
                return float(b.get("free", 0))
    except Exception:
        return None
    return None


def build_snapshot_md(positions: List[Position], prices: Dict[str, float],
                      usdt_balance: Optional[float]) -> str:
    """Format a markdown snapshot.

    - Balance line only emitted if usdt_balance is not None.
    - Positions rendered as markdown code-block table (Discord embed-friendly).
    - When current price is unavailable, P&L shows "-".
    - When positions is empty, shows "(無持倉)".
    """
    parts: List[str] = []
    if usdt_balance is not None:
        parts.append(f"**目前餘額** USDT ${usdt_balance:,.2f}")

    parts.append("**目前持有**")
    if not positions:
        parts.append("```\n(無持倉)\n```")
    else:
        rows = [
            "```",
            "| 幣別      | 數量        | 成本價       | 損益值     |",
            "|-----------|-------------|--------------|------------|",
        ]
        for p in positions:
            curr = prices.get(p.symbol)
            if curr is not None:
                pnl = (curr - p.avg_entry) * p.qty
                pnl_str = f"${pnl:+,.2f}"
            else:
                pnl_str = "-"
            rows.append(
                f"| {p.symbol:<9} | {p.qty:>11.6f} | ${p.avg_entry:>10,.2f} | {pnl_str:>9} |"
            )
        rows.append("```")
        parts.append("\n".join(rows))

    return "\n".join(parts)


def gather_snapshot(db: Database, exchange) -> str:
    """End-to-end: read positions, fetch prices+balance, format markdown.

    Returns "" if anything catastrophically fails (caller can skip attach).
    """
    try:
        positions = Positions(db).list_all()
        symbols = [p.symbol for p in positions]
        prices = fetch_prices_for_positions(exchange, symbols)
        balance = fetch_usdt_balance(exchange)
        return build_snapshot_md(positions, prices, balance)
    except Exception:
        return ""
