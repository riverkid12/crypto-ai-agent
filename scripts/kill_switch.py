"""Toggle kill_switch on Turso.

Usage:
    python -m scripts.kill_switch --on    # set control.kill_switch = 'true'
    python -m scripts.kill_switch --off   # set control.kill_switch = 'false'
    python -m scripts.kill_switch         # show current value (no change)
"""
import argparse
import os
import sys
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
from db.repos.control import Control


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--on", action="store_true", help="set kill_switch = true")
    group.add_argument("--off", action="store_true", help="set kill_switch = false")
    args = parser.parse_args()

    url = os.environ.get("TURSO_DB_URL") or os.environ.get("DB_URL", "")
    token = os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get("DB_AUTH_TOKEN", "")
    if not url:
        print("ERROR: DB_URL not set", file=sys.stderr)
        return 1

    with Database(url, auth_token=token if token else None) as db:
        c = Control(db)
        before = c.get_bool("kill_switch", default=False)

        if args.on:
            c.set("kill_switch", "true")
            print(f"kill_switch: {before} -> True  (ALL new entries blocked; closes/stops still allowed)")
        elif args.off:
            c.set("kill_switch", "false")
            print(f"kill_switch: {before} -> False  (system back to normal)")
        else:
            print(f"kill_switch: {before}  (use --on or --off to change)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
