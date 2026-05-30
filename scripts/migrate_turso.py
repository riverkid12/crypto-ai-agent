"""One-shot migration runner for Turso (or local sqlite for testing).

Usage:
    # For Turso: set TURSO_DB_URL and TURSO_AUTH_TOKEN in .env or env
    python -m scripts.migrate_turso

    # For local sqlite test:
    DB_URL=sqlite:///state/local.db python -m scripts.migrate_turso
"""
import os
import sys
from pathlib import Path

# Load .env if present
_env_path = Path(__file__).resolve().parents[1] / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from db.client import Database
from schema.migrate import migrate


def main() -> int:
    url = os.environ.get("TURSO_DB_URL") or os.environ.get("DB_URL", "")
    token = os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get("DB_AUTH_TOKEN", "")
    if not url:
        print("ERROR: TURSO_DB_URL (or DB_URL) not set", file=sys.stderr)
        return 1
    if url.startswith("libsql://") and not token:
        print("ERROR: TURSO_AUTH_TOKEN (or DB_AUTH_TOKEN) not set for libsql", file=sys.stderr)
        return 1

    print(f"Connecting to: {url}")
    with Database(url, auth_token=token if token else None) as db:
        applied = migrate(db)
        print(f"Applied versions: {applied}")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
