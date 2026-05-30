"""Seed a test signal into the cloud DB.

Usage:
    python -m scripts.seed_signal                            # default: BTCUSDT market $50
    python -m scripts.seed_signal --symbol ETHUSDT --size 100
    python -m scripts.seed_signal --symbol BTCUSDT --entry 60000 --stop 58000 --target 65000 --size 50
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Load .env
_env_path = Path(__file__).resolve().parents[1] / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from db.client import Database
from db.repos.signals import Signals
from db.repos.strategies import Strategies


DEFAULT_UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair (default: BTCUSDT)")
    parser.add_argument("--size", type=float, default=50.0, help="Position size in USDT (default: 50)")
    parser.add_argument("--entry", type=float, default=None,
                        help="Entry price (omit = market entry)")
    parser.add_argument("--stop", type=float, default=None, help="Stop-loss price")
    parser.add_argument("--target", type=float, default=None, help="Take-profit price")
    parser.add_argument("--expires-hours", type=int, default=24,
                        help="Signal expiry in hours (default: 24)")
    parser.add_argument("--strategy", default="trend_majors", help="Strategy name (default: trend_majors)")
    parser.add_argument("--reason", default="manual seed (P1 smoke)", help="Reason text")
    args = parser.parse_args()

    url = os.environ.get("TURSO_DB_URL") or os.environ.get("DB_URL", "")
    token = os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get("DB_AUTH_TOKEN", "")
    if not url:
        print("ERROR: TURSO_DB_URL not set", file=sys.stderr)
        return 1

    expires_at = (datetime.now(timezone.utc) + timedelta(hours=args.expires_hours)).isoformat()

    with Database(url, auth_token=token if token else None) as db:
        # Ensure strategy exists with default universe (idempotent)
        strategies = Strategies(db)
        strategy = strategies.get_by_name(args.strategy)
        if strategy is None:
            sid = strategies.insert(name=args.strategy, params={"universe": DEFAULT_UNIVERSE})
            print(f"Inserted new strategy '{args.strategy}' with universe {DEFAULT_UNIVERSE}, id={sid}")
        else:
            sid = strategy.id
            print(f"Using existing strategy '{args.strategy}' id={sid}, universe={strategy.params.get('universe')}")

        signals = Signals(db)
        signal_id = signals.insert(
            strategy_id=sid, symbol=args.symbol, side="long",
            entry_price=args.entry, stop_price=args.stop, target_price=args.target,
            size_usdt=args.size, expires_at=expires_at, reason=args.reason,
        )
        print(f"Inserted signal: id={signal_id} symbol={args.symbol} size_usdt={args.size} "
              f"entry={args.entry} stop={args.stop} target={args.target}")
        print(f"Expires: {expires_at}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
