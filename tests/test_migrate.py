from db.client import Database
from schema.migrate import migrate


def test_migrate_creates_all_tables():
    db = Database(":memory:")
    migrate(db)
    tables = {row[0] for row in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables >= {
        "strategies", "signals", "orders", "positions",
        "pnl_daily", "control", "events", "schema_version",
    }


def test_migrate_is_idempotent():
    db = Database(":memory:")
    migrate(db)
    migrate(db)  # 再跑一次不爆
    versions = db.query("SELECT version FROM schema_version ORDER BY version")
    assert versions == [(1,), (2,)]  # 001 + 002 各一次,不重複套用


def test_migrate_records_version():
    db = Database(":memory:")
    migrate(db)
    versions = {row[0] for row in db.query("SELECT version FROM schema_version")}
    assert 1 in versions
