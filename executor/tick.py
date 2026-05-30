"""Main tick loop: read signals -> match -> check risk -> place order -> update state.

P0 scope:
- Entry (market or long-side breakout)
- No stop/target/flat exit (P2)
- daily_realized_pnl always 0 (P3 adds pnl calculation)
"""
import argparse
import os
import sys
from adapters.exchanges._fake import FakeExchange
from adapters.exchanges.base import Exchange
from db.client import Database
from db.repos.control import Control
from db.repos.events import Events
from db.repos.orders import Orders
from db.repos.positions import Positions
from db.repos.signals import Signals
from db.repos.strategies import Strategies
from executor.circuit_breaker import CircuitBreaker
from executor.matcher import should_trigger
from schema.migrate import migrate


def run_tick(db: Database, exchange: Exchange,
             strategy_name: str = "trend_majors") -> dict:
    strategies = Strategies(db)
    signals = Signals(db)
    orders = Orders(db)
    positions = Positions(db)
    events = Events(db)
    cb = CircuitBreaker(Control(db), positions, events)

    strategy = strategies.get_by_name(strategy_name)
    if strategy is None:
        events.log("error", {"msg": f"strategy not found: {strategy_name}"})
        return {"triggered": 0, "blocked": 0, "api_errors": 0}

    universe = strategy.params.get("universe", [])
    summary = {"triggered": 0, "blocked": 0, "api_errors": 0}

    for sig in signals.list_active():
        # 0. universe pre-check (avoid unnecessary API call)
        if sig.symbol not in universe:
            events.log("blocked", {
                "signal_id": sig.id, "symbol": sig.symbol,
                "reason": f"universe: {sig.symbol} not in whitelist",
            })
            summary["blocked"] += 1
            continue

        # 0b. per-symbol API circuit (skip if prior failures hit threshold)
        if cb.should_circuit_open(sig.symbol):
            events.log("blocked", {
                "signal_id": sig.id, "symbol": sig.symbol,
                "reason": f"circuit_open: api failures for {sig.symbol} >= threshold",
            })
            summary["blocked"] += 1
            continue

        # 1. get current price
        try:
            current_price = exchange.get_price(sig.symbol)
        except Exception as exc:
            cb.note_api_failure(sig.symbol)
            events.log("error", {
                "phase": "get_price", "symbol": sig.symbol, "err": str(exc),
            })
            summary["api_errors"] += 1
            continue

        # 2. matcher
        holding = positions.get_qty(sig.symbol)
        if not should_trigger(sig, current_price, holding_qty=holding):
            continue

        # 3. circuit breaker (P0: daily_realized_pnl=0)
        reason = cb.evaluate_new_entry(
            symbol=sig.symbol, size_usdt=sig.size_usdt,
            universe=universe, daily_realized_pnl=0.0,
        )
        if reason is not None:
            events.log("blocked", {
                "signal_id": sig.id, "symbol": sig.symbol, "reason": reason,
            })
            summary["blocked"] += 1
            continue

        # 4. place order (market only in P0)
        qty = sig.size_usdt / current_price
        order_id = orders.insert(
            signal_id=sig.id, exchange_order_id=None,
            symbol=sig.symbol, side="buy", qty=qty,
            price=None, type="market", status="new",
        )
        try:
            ex_order = exchange.place_order(sig.symbol, "buy", qty, type="market")
        except Exception as exc:
            cb.note_api_failure(sig.symbol)
            events.log("error", {
                "phase": "place_order", "symbol": sig.symbol, "err": str(exc),
            })
            summary["api_errors"] += 1
            continue

        if ex_order.status != "filled":
            cb.note_api_failure(sig.symbol)
            events.log("error", {
                "phase": "fill", "symbol": sig.symbol, "status": ex_order.status,
            })
            summary["api_errors"] += 1
            continue

        # 5. write back state
        orders.update_fill(
            order_id, fill_qty=ex_order.fill_qty,
            fill_price=ex_order.fill_price, fee_usdt=ex_order.fee_usdt,
            status="filled",
        )
        positions.upsert(sig.symbol, qty=ex_order.fill_qty,
                         avg_entry=ex_order.fill_price, current_price=current_price)
        cb.note_api_success(sig.symbol)
        signals.mark_triggered(sig.id)
        events.log("fill", {
            "signal_id": sig.id, "symbol": sig.symbol,
            "qty": ex_order.fill_qty, "price": ex_order.fill_price,
            "fee_usdt": ex_order.fee_usdt,
        })
        summary["triggered"] += 1

    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fake", action="store_true",
                        help="use FakeExchange + in-memory data for smoke test")
    parser.add_argument("--strategy", default="trend_majors")
    args = parser.parse_args()

    if args.fake:
        db = Database(":memory:")
        migrate(db)
        Strategies(db).insert(name="trend_majors",
                              params={"universe": ["BTCUSDT", "ETHUSDT", "SOLUSDT"]})
        from datetime import datetime, timedelta, timezone
        expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        Signals(db).insert(
            strategy_id=1, symbol="BTCUSDT", side="long",
            entry_price=None, stop_price=58000.0, target_price=65000.0,
            size_usdt=300.0, expires_at=expires, reason="fake smoke signal",
        )
        ex = FakeExchange()
        ex.set_price("BTCUSDT", 60000.0)
        ex.set_price("ETHUSDT", 3000.0)
        ex.set_price("SOLUSDT", 150.0)
        summary = run_tick(db, ex, strategy_name=args.strategy)
        print(f"[fake tick] summary: {summary}")
        for pos in Positions(db).list_all():
            print(f"  position: {pos.symbol} qty={pos.qty:.6f} avg_entry={pos.avg_entry}")
        return 0

    db_url = os.environ.get("DB_URL", "sqlite:///state/local.db")
    with Database(db_url) as db:
        # P0 does not connect to Binance; non-fake mode is rejected
        print("non-fake mode requires Binance adapter (P1).", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
