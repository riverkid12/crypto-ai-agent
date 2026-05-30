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


def test_seed_inserts_default_controls():
    db = Database(":memory:")
    migrate(db)
    rows = db.query("SELECT key, value FROM control ORDER BY key")
    keys = {r[0]: r[1] for r in rows}
    assert keys["kill_switch"] == "false"
    assert keys["max_per_trade_usdt"] == "500"
    assert keys["max_daily_loss_usdt"] == "300"
    assert keys["max_open_positions"] == "3"
    assert keys["max_position_per_symbol"] == "1"
    assert keys["api_fail_threshold"] == "3"
    assert keys["slippage_max_pct"] == "0.01"
    assert keys["signal_default_expiry_hours"] == "24"
    assert keys["exec_tick_interval_minutes"] == "5"
    assert keys["cowork_decision_time_tw"] == "21:00"
    assert keys["bridge_run_time_tw"] == "21:05"
    assert keys["daily_report_time_tw"] == "23:55"
    assert keys["notify_dedup_window_minutes"] == "10"
