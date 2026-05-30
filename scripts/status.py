"""One-shot status dashboard for crypto-ai-agent.

Usage:
    python -m scripts.status                # one snapshot
    python -m scripts.status --watch        # refresh every 10s
    python -m scripts.status --no-exchange  # skip Binance call (e.g., when offline)
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
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


def _fmt_money(v, dp=2):
    if v is None:
        return "-"
    return f"${v:,.{dp}f}"


def _fmt_qty(v, dp=6):
    if v is None:
        return "-"
    return f"{v:.{dp}f}"


def _fmt_ts(ts):
    if not ts:
        return "-"
    # Strip microseconds + tz for display
    try:
        return ts[:19].replace("T", " ")
    except Exception:
        return ts


def _section(title):
    print()
    print(f"=== {title} ===")


def snapshot(skip_exchange: bool = False) -> None:
    url = os.environ.get("TURSO_DB_URL") or os.environ.get("DB_URL", "")
    token = os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get("DB_AUTH_TOKEN", "")
    if not url:
        print("ERROR: DB_URL not set", file=sys.stderr)
        sys.exit(1)

    print(f"crypto-ai-agent  status  @  {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    print(f"DB: {url}")

    with Database(url, auth_token=token if token else None) as db:
        # Positions
        _section("Positions")
        positions = db.query(
            "SELECT symbol, qty, avg_entry, current_price, unrealized_pnl, updated_at "
            "FROM positions ORDER BY symbol"
        )
        if not positions:
            print("  (none)")
        else:
            print(f"  {'SYMBOL':<12} {'QTY':>14} {'AVG_ENTRY':>14} {'CURRENT':>14} {'UNREAL_PNL':>14}  UPDATED")
            for sym, qty, avg, cur, pnl, upd in positions:
                print(f"  {sym:<12} {_fmt_qty(qty):>14} {_fmt_money(avg):>14} "
                      f"{_fmt_money(cur):>14} {_fmt_money(pnl):>14}  {_fmt_ts(upd)}")

        # Active signals
        _section("Active Signals (status=pending, not expired)")
        now_iso = datetime.now(timezone.utc).isoformat()
        active = db.query(
            "SELECT id, symbol, side, entry_price, stop_price, target_price, size_usdt, expires_at "
            "FROM signals WHERE status = 'pending' AND (expires_at IS NULL OR expires_at > ?) "
            "ORDER BY id DESC",
            (now_iso,),
        )
        if not active:
            print("  (none)")
        else:
            print(f"  {'ID':>4} {'SYMBOL':<12} {'SIDE':<6} {'ENTRY':>12} {'STOP':>12} {'TARGET':>12} {'SIZE':>10}  EXPIRES")
            for sid, sym, side, ent, stp, tgt, size, exp in active:
                print(f"  {sid:>4} {sym:<12} {side:<6} {_fmt_money(ent):>12} "
                      f"{_fmt_money(stp):>12} {_fmt_money(tgt):>12} {_fmt_money(size):>10}  {_fmt_ts(exp)}")

        # Recent orders
        _section("Recent Orders (last 10)")
        orders = db.query(
            "SELECT id, symbol, side, qty, fill_price, fee_usdt, status, created_at, filled_at "
            "FROM orders ORDER BY id DESC LIMIT 10"
        )
        if not orders:
            print("  (none)")
        else:
            print(f"  {'ID':>4} {'SYMBOL':<10} {'SIDE':<5} {'QTY':>12} {'FILL':>12} {'FEE':>8}  STATUS    CREATED")
            for oid, sym, side, qty, fill, fee, st, cr, fl in orders:
                print(f"  {oid:>4} {sym:<10} {side:<5} {_fmt_qty(qty):>12} "
                      f"{_fmt_money(fill):>12} {_fmt_money(fee, 4):>8}  {st:<8}  {_fmt_ts(cr)}")

        # Recent signals
        _section("Recent Signals (last 5)")
        sigs = db.query(
            "SELECT id, symbol, side, size_usdt, status, reason, created_at "
            "FROM signals ORDER BY id DESC LIMIT 5"
        )
        if not sigs:
            print("  (none)")
        else:
            for sid, sym, side, size, st, reason, cr in sigs:
                reason_short = (reason or "")[:60]
                print(f"  #{sid} {sym} {side} size={_fmt_money(size)} status={st}  ({_fmt_ts(cr)})  {reason_short}")

        # Recent events
        _section("Recent Events (last 10)")
        events = db.query(
            "SELECT id, type, payload_json, created_at FROM events ORDER BY id DESC LIMIT 10"
        )
        if not events:
            print("  (none)")
        else:
            for eid, etype, payload, cr in events:
                try:
                    p = json.loads(payload)
                    sym = p.get("symbol", "")
                    if etype == "fill":
                        msg = f"{sym} qty={p.get('qty')} @ {_fmt_money(p.get('price'))}"
                    elif etype == "blocked":
                        msg = f"{sym} reason={p.get('reason', '')}"
                    elif etype == "error":
                        msg = f"{p.get('phase', '')} {sym} err={p.get('err', '')[:60]}"
                    else:
                        msg = str(p)[:100]
                except Exception:
                    msg = payload[:100]
                print(f"  [{_fmt_ts(cr)}] {etype:<14} {msg}")

        # Control flags (key ones)
        _section("Control Flags")
        keys = [
            "kill_switch", "max_per_trade_usdt", "max_daily_loss_usdt",
            "max_open_positions", "max_position_per_symbol",
            "api_fail_threshold", "slippage_max_pct",
        ]
        placeholders = ",".join("?" * len(keys))
        ctrl = db.query(f"SELECT key, value FROM control WHERE key IN ({placeholders}) ORDER BY key", keys)
        for k, v in ctrl:
            mark = "  KILL ENABLED" if (k == "kill_switch" and v.lower() == "true") else ""
            print(f"  {k:<28} = {v}{mark}")

        # Daily P&L
        _section("Daily P&L (last 7 days)")
        pnl = db.query(
            "SELECT date, realized_pnl, unrealized_pnl, equity, trades_count "
            "FROM pnl_daily ORDER BY date DESC LIMIT 7"
        )
        if not pnl:
            print("  (none - P&L reporter not yet wired, coming in P3)")
        else:
            for d, r, u, eq, n in pnl:
                print(f"  {d}  realized={_fmt_money(r)}  unreal={_fmt_money(u)}  equity={_fmt_money(eq)}  trades={n}")

    # Binance testnet balances + open orders
    if not skip_exchange:
        _section("Binance Testnet Account")
        api_key = os.environ.get("BINANCE_API_KEY", "")
        api_secret = os.environ.get("BINANCE_API_SECRET", "")
        if not api_key or not api_secret:
            print("  (BINANCE_API_KEY/SECRET not set; --no-exchange to suppress this section)")
        else:
            try:
                from binance.client import Client
                testnet = os.environ.get("BINANCE_TESTNET", "true").lower() == "true"
                c = Client(api_key, api_secret, testnet=testnet)
                acct = c.get_account()
                balances = [
                    b for b in acct["balances"]
                    if float(b["free"]) > 0 or float(b["locked"]) > 0
                ]
                if not balances:
                    print("  (no balances)")
                else:
                    print(f"  {'ASSET':<8} {'FREE':>16} {'LOCKED':>16}")
                    for b in balances:
                        asset = b['asset'].encode("ascii", errors="replace").decode("ascii")
                        print(f"  {asset:<8} {b['free']:>16} {b['locked']:>16}")

                open_orders = c.get_open_orders()
                if open_orders:
                    print("  Open orders:")
                    for o in open_orders:
                        print(f"    #{o['orderId']} {o['symbol']} {o['side']} {o['origQty']} @ {o.get('price', '-')}")
                else:
                    print("  Open orders: (none)")
            except Exception as exc:
                err_msg = str(exc).encode("ascii", errors="replace").decode("ascii")
                print(f"  ERROR: {type(exc).__name__}: {err_msg}")

    print()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true",
                        help="Re-snapshot every 10 seconds")
    parser.add_argument("--interval", type=int, default=10,
                        help="Watch interval in seconds (default 10)")
    parser.add_argument("--no-exchange", action="store_true",
                        help="Skip Binance API call (offline mode)")
    args = parser.parse_args()

    if not args.watch:
        snapshot(skip_exchange=args.no_exchange)
        return 0

    # Watch mode
    try:
        while True:
            # Clear screen (ANSI on Unix; on Windows, just print separator)
            if os.name == "nt":
                os.system("cls")
            else:
                print("\033[2J\033[H", end="")
            snapshot(skip_exchange=args.no_exchange)
            print(f"--- refresh in {args.interval}s --- (Ctrl+C to exit)")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
