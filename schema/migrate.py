"""Apply schema/*.sql files in order, recording each in schema_version."""
import re
from datetime import datetime, timezone
from pathlib import Path
from db.client import Database

SCHEMA_DIR = Path(__file__).parent
FILENAME_RE = re.compile(r"^(\d+)_.+\.sql$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_version_table(db: Database) -> None:
    db.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )


def _applied_versions(db: Database) -> set[int]:
    rows = db.query("SELECT version FROM schema_version")
    return {r[0] for r in rows}


def migrate(db: Database) -> list[int]:
    """Apply any *.sql in SCHEMA_DIR whose leading number is not yet applied.

    Returns the list of versions applied this call.
    """
    _ensure_version_table(db)
    applied = _applied_versions(db)
    files = sorted(SCHEMA_DIR.glob("*.sql"))
    newly = []
    for f in files:
        m = FILENAME_RE.match(f.name)
        if not m:
            continue
        version = int(m.group(1))
        if version in applied:
            continue
        sql = f.read_text(encoding="utf-8")
        db.executescript(sql)
        db.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, _now()),
        )
        newly.append(version)
    return newly


if __name__ == "__main__":
    import os
    url = os.environ.get("DB_URL", "sqlite:///state/local.db")
    with Database(url) as db:
        applied = migrate(db)
        print(f"applied versions: {applied}")
