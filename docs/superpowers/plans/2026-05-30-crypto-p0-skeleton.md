# crypto-ai-agent P0 (骨架) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 spec 第 11 節 P0 跑出來:repo 結構、本地 SQLite schema、fake exchange、circuit breaker、matcher、tick orchestrator,e2e 走得通,`pytest tests/ -v` 全綠,`python -m executor.tick --fake` 能看到模擬交易。

**Architecture:** P0 全部跑在本機,**不接 Turso、不接 Binance、不接 GitHub Actions**。DB 用 `sqlite3` 模組寫一個薄包裝,介面設計成可以無痛換成 libSQL(P1 接 Turso 時改連線初始化即可)。所有 repo 都是純 dataclass + 純 SQL,exchange 走 Protocol + Fake 實作。Cron/HTTP/外網 完全留到 P1。

**Tech Stack:** Python 3.11+、`sqlite3`(stdlib)、`pytest`、`pytest-cov`、`python-dateutil`。

---

## 重要紀律(每個 task 都要遵守)

來自 stock 專案踩坑筆記(`C:\Users\riverkid\.claude\CLAUDE.md`):

1. **改 .py 後**:跑測試前先 `touch <file>`(Windows 掛載目錄 .pyc 不會被 sandbox 刪)。本機開發環境如果沒有這問題可以略過,但放心 touch 不會壞事。
2. **批次檔純 ASCII**:P0 內所有 `.bat` 內容只用英文,首行 `chcp 65001 > nul`。
3. **長檔走 heredoc**:任何 > 100 行的 Python/Markdown 都用 `cat > file << 'EOF'` 寫。本 plan 的程式碼小檔不受此限。
4. **四連驗證**(每個 task 完工前):
   - `wc -l <檔>` + `tail -5 <檔>` 確認沒被截斷
   - `python -c "import <mod>"` 確認載得進
   - `python -m compileall -q <dir>` 語法檢查
   - 跑該 task 的 pytest

## 整體流程

| Task | 主題 | 約時 |
|---|---|---|
| 1 | Bootstrap(requirements / pytest / dir / conftest)| 10 min |
| 2 | DB client(sqlite3 wrapper)| 10 min |
| 3 | Schema 001_init.sql + migrate.py | 15 min |
| 4 | Schema 002_seed.sql(預設 control 值)| 10 min |
| 5 | Control repo(typed get/set)| 15 min |
| 6 | Strategies repo | 10 min |
| 7 | Signals repo | 15 min |
| 8 | Orders repo | 10 min |
| 9 | Positions repo(upsert)| 15 min |
| 10 | Events repo | 5 min |
| 11 | Exchange Protocol + ExchangeOrder dataclass | 10 min |
| 12 | Fake exchange | 15 min |
| 13 | Matcher(signal trigger 判斷)| 15 min |
| 14 | Circuit breaker(kill switch + caps)| 20 min |
| 15 | Tick orchestrator + CLI entry | 25 min |
| 16 | E2E test + 最終驗收 | 15 min |

**約 3.5 小時專注時間能跑完 P0。**

---

## File Structure(P0 結束時的 repo 樣貌)

```
C:\Projects\crypto-ai-agent\
├── .gitignore                  (已有)
├── .env.example                (P0 新增)
├── pyproject.toml              (P0 新增,pytest 設定)
├── requirements.txt            (P0 新增)
├── conftest.py                 (P0 新增,讓 pytest 找得到 root modules)
├── adapters\
│   ├── __init__.py
│   └── exchanges\
│       ├── __init__.py
│       ├── base.py             Exchange Protocol + ExchangeOrder dataclass
│       └── _fake.py            in-memory fake exchange
├── db\
│   ├── __init__.py
│   ├── client.py               sqlite3 連線包裝(connection string from env)
│   └── repos\
│       ├── __init__.py
│       ├── control.py
│       ├── strategies.py
│       ├── signals.py
│       ├── orders.py
│       ├── positions.py
│       └── events.py
├── executor\
│   ├── __init__.py
│   ├── matcher.py              signal vs current price 觸發判斷
│   ├── circuit_breaker.py      kill switch + 每筆/每日/同時持倉上限
│   └── tick.py                 主迴圈 + CLI entry(`python -m executor.tick --fake`)
├── schema\
│   ├── 001_init.sql            建所有表
│   ├── 002_seed.sql            插入 control 預設值
│   └── migrate.py              讀 schema/*.sql 套到 DB
├── tests\
│   ├── __init__.py
│   ├── conftest.py             共用 fixtures(in-memory DB、fake exchange)
│   ├── test_db_client.py
│   ├── test_migrate.py
│   ├── test_control.py
│   ├── test_strategies.py
│   ├── test_signals.py
│   ├── test_orders.py
│   ├── test_positions.py
│   ├── test_events.py
│   ├── test_fake_exchange.py
│   ├── test_matcher.py
│   ├── test_circuit_breaker.py
│   └── test_tick_e2e.py
├── state\                      (.gitignore'd, 本機 SQLite 檔放這)
└── docs\superpowers\...        (已有)
```

P0 沒做的(留給後續):`pipeline/`、`bridge/`、`strategies/<name>/`、`_START_HERE/`、`.github/workflows/`、Binance adapter、chat-notify-hub 接線。

---

## Task 1: Bootstrap

**Files:**
- Create: `C:\Projects\crypto-ai-agent\requirements.txt`
- Create: `C:\Projects\crypto-ai-agent\.env.example`
- Create: `C:\Projects\crypto-ai-agent\pyproject.toml`
- Create: `C:\Projects\crypto-ai-agent\conftest.py`
- Create: `C:\Projects\crypto-ai-agent\tests\__init__.py`
- Create: empty `__init__.py` 在 `adapters/`、`adapters/exchanges/`、`db/`、`db/repos/`、`executor/`

- [ ] **Step 1.1: 建 requirements.txt**

```
pytest==8.3.3
pytest-cov==5.0.0
python-dateutil==2.9.0
```

- [ ] **Step 1.2: 建 .env.example**

```
# Database
# 本機 P0 用:DB_URL=sqlite:///state/local.db
# Turso(P1+):DB_URL=libsql://<your-db>.turso.io  + DB_AUTH_TOKEN=<token>
DB_URL=sqlite:///state/local.db
DB_AUTH_TOKEN=

# Exchange(P1+)
BINANCE_API_KEY=
BINANCE_API_SECRET=
BINANCE_TESTNET=true

# Notify(P3+)
CHAT_NOTIFY_HUB_URL=
```

- [ ] **Step 1.3: 建 pyproject.toml(pytest 設定)**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"
```

- [ ] **Step 1.4: 建 conftest.py(讓 pytest 在 root 也能 import)**

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
```

- [ ] **Step 1.5: 建空 `__init__.py`**

```bash
touch adapters/__init__.py
touch adapters/exchanges/__init__.py
touch db/__init__.py
touch db/repos/__init__.py
touch executor/__init__.py
touch tests/__init__.py
```

- [ ] **Step 1.6: 裝依賴 + 驗證**

```bash
cd /c/Projects/crypto-ai-agent
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
pytest --version
```

Expected: `pytest 8.3.3`

- [ ] **Step 1.7: Commit**

```bash
git add requirements.txt .env.example pyproject.toml conftest.py adapters/ db/ executor/ tests/__init__.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "chore(p0): bootstrap project (pytest, env example, package skeleton)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: DB Client

**Files:**
- Create: `db/client.py`
- Create: `tests/test_db_client.py`

- [ ] **Step 2.1: 寫測試**

`tests/test_db_client.py`:

```python
import pytest
from db.client import Database


def test_in_memory_db_executes_and_queries():
    db = Database(":memory:")
    db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    db.execute("INSERT INTO t (name) VALUES (?)", ("alice",))
    rows = db.query("SELECT id, name FROM t")
    assert rows == [(1, "alice")]


def test_query_one_returns_single_row_or_none():
    db = Database(":memory:")
    db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    assert db.query_one("SELECT * FROM t WHERE id = ?", (1,)) is None
    db.execute("INSERT INTO t (name) VALUES (?)", ("bob",))
    assert db.query_one("SELECT name FROM t WHERE id = ?", (1,)) == ("bob",)


def test_execute_returns_lastrowid():
    db = Database(":memory:")
    db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    rowid = db.execute("INSERT INTO t (name) VALUES (?)", ("carol",))
    assert rowid == 1
    rowid2 = db.execute("INSERT INTO t (name) VALUES (?)", ("dave",))
    assert rowid2 == 2


def test_context_manager_closes():
    with Database(":memory:") as db:
        db.execute("CREATE TABLE t (x INTEGER)")
    # after exit, queries should fail
    with pytest.raises(Exception):
        db.query("SELECT 1")
```

- [ ] **Step 2.2: 跑測試,確認 fail**

```bash
pytest tests/test_db_client.py -v
```

Expected: ImportError / ModuleNotFoundError for `db.client`

- [ ] **Step 2.3: 寫 db/client.py**

```python
"""Thin wrapper over sqlite3 with a connection-string API.

P0 只支援 sqlite (in-memory 或 file)。P1 會新增 libsql:// scheme 切到 Turso。
"""
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple, List


class Database:
    def __init__(self, url: str):
        self._url = url
        path = self._parse(url)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA foreign_keys = ON")

    @staticmethod
    def _parse(url: str) -> str:
        if url == ":memory:":
            return ":memory:"
        if url.startswith("sqlite:///"):
            return url[len("sqlite:///"):]
        if url.startswith("sqlite://"):
            return url[len("sqlite://"):]
        raise ValueError(f"unsupported DB url: {url} (P0 only supports sqlite)")

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        cur = self._conn.execute(sql, tuple(params))
        self._conn.commit()
        return cur.lastrowid

    def executescript(self, script: str) -> None:
        self._conn.executescript(script)
        self._conn.commit()

    def query(self, sql: str, params: Iterable[Any] = ()) -> List[Tuple]:
        cur = self._conn.execute(sql, tuple(params))
        return cur.fetchall()

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> Optional[Tuple]:
        cur = self._conn.execute(sql, tuple(params))
        return cur.fetchone()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
```

- [ ] **Step 2.4: 跑測試,確認 pass**

```bash
pytest tests/test_db_client.py -v
```

Expected: 4 passed

- [ ] **Step 2.5: Commit**

```bash
git add db/client.py tests/test_db_client.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): add Database wrapper over sqlite3

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Schema Migration

**Files:**
- Create: `schema/001_init.sql`
- Create: `schema/migrate.py`
- Create: `tests/test_migrate.py`

- [ ] **Step 3.1: 寫 schema/001_init.sql**

```sql
CREATE TABLE strategies (
  id           INTEGER PRIMARY KEY,
  name         TEXT UNIQUE NOT NULL,
  params_json  TEXT NOT NULL,
  active       INTEGER NOT NULL DEFAULT 1,
  updated_at   TEXT NOT NULL
);

CREATE TABLE signals (
  id            INTEGER PRIMARY KEY,
  strategy_id   INTEGER NOT NULL REFERENCES strategies(id),
  symbol        TEXT NOT NULL,
  side          TEXT NOT NULL,
  entry_price   REAL,
  stop_price    REAL,
  target_price  REAL,
  size_usdt     REAL NOT NULL,
  status        TEXT NOT NULL,
  reason        TEXT,
  expires_at    TEXT,
  created_at    TEXT NOT NULL
);
CREATE INDEX idx_signals_status ON signals(status, expires_at);

CREATE TABLE orders (
  id                INTEGER PRIMARY KEY,
  signal_id         INTEGER REFERENCES signals(id),
  exchange_order_id TEXT,
  symbol            TEXT NOT NULL,
  side              TEXT NOT NULL,
  qty               REAL NOT NULL,
  price             REAL,
  type              TEXT NOT NULL,
  status            TEXT NOT NULL,
  fill_qty          REAL DEFAULT 0,
  fill_price        REAL,
  fee_usdt          REAL DEFAULT 0,
  created_at        TEXT NOT NULL,
  filled_at         TEXT
);

CREATE TABLE positions (
  symbol           TEXT PRIMARY KEY,
  qty              REAL NOT NULL,
  avg_entry        REAL NOT NULL,
  current_price    REAL,
  unrealized_pnl   REAL,
  updated_at       TEXT NOT NULL
);

CREATE TABLE pnl_daily (
  date             TEXT PRIMARY KEY,
  realized_pnl     REAL NOT NULL,
  unrealized_pnl   REAL NOT NULL,
  equity           REAL NOT NULL,
  trades_count     INTEGER NOT NULL
);

CREATE TABLE control (
  key         TEXT PRIMARY KEY,
  value       TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

CREATE TABLE events (
  id            INTEGER PRIMARY KEY,
  type          TEXT NOT NULL,
  payload_json  TEXT NOT NULL,
  created_at    TEXT NOT NULL
);
CREATE INDEX idx_events_created ON events(created_at);

CREATE TABLE schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
```

- [ ] **Step 3.2: 寫 tests/test_migrate.py**

```python
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
```

- [ ] **Step 3.3: 寫 schema/migrate.py**

```python
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
```

- [ ] **Step 3.4: 跑測試**

```bash
pytest tests/test_migrate.py -v
```

Expected: 注意 test_migrate_is_idempotent 期望 `[(1,), (2,)]`,所以下一個 task(002_seed)要在這之前準備好。先跳到 Task 4 完成 002_seed.sql,再回來跑這個測試。

實際上更乾淨的作法:**現在先用 placeholder** — Task 3.4 改成只跑 `test_migrate_creates_all_tables` 和 `test_migrate_records_version`:

```bash
pytest tests/test_migrate.py::test_migrate_creates_all_tables tests/test_migrate.py::test_migrate_records_version -v
```

Expected: 2 passed.

`test_migrate_is_idempotent` 等 Task 4 寫完 002_seed.sql 後再跑。

- [ ] **Step 3.5: Commit**

```bash
git add schema/001_init.sql schema/migrate.py tests/test_migrate.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): add schema 001_init + migrate runner

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Schema 002_seed (control 預設值)

**Files:**
- Create: `schema/002_seed.sql`

- [ ] **Step 4.1: 寫 schema/002_seed.sql**

```sql
-- 預設 control 值(對應 spec section 6 的 seed 清單)
INSERT INTO control (key, value, updated_at) VALUES
  ('kill_switch', 'false', datetime('now')),
  ('max_per_trade_usdt', '500', datetime('now')),
  ('max_daily_loss_usdt', '300', datetime('now')),
  ('max_open_positions', '3', datetime('now')),
  ('max_position_per_symbol', '1', datetime('now')),
  ('api_fail_threshold', '3', datetime('now')),
  ('slippage_max_pct', '0.01', datetime('now')),
  ('signal_default_expiry_hours', '24', datetime('now')),
  ('cowork_decision_time_tw', '21:00', datetime('now')),
  ('bridge_run_time_tw', '21:05', datetime('now')),
  ('daily_report_time_tw', '23:55', datetime('now')),
  ('exec_tick_interval_minutes', '5', datetime('now')),
  ('notify_dedup_window_minutes', '10', datetime('now'));
```

- [ ] **Step 4.2: 跑完整 migrate 測試**

```bash
pytest tests/test_migrate.py -v
```

Expected: 3 passed(含 test_migrate_is_idempotent)。

- [ ] **Step 4.3: 加一個 seed 內容測試**

Append to `tests/test_migrate.py`:

```python
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
```

```bash
pytest tests/test_migrate.py::test_seed_inserts_default_controls -v
```

Expected: passed.

- [ ] **Step 4.4: Commit**

```bash
git add schema/002_seed.sql tests/test_migrate.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): add schema 002_seed with default control values

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Control Repository

**Files:**
- Create: `db/repos/control.py`
- Create: `tests/conftest.py`(共用 fixture)
- Create: `tests/test_control.py`

- [ ] **Step 5.1: 寫 tests/conftest.py**

```python
import pytest
from db.client import Database
from schema.migrate import migrate


@pytest.fixture
def db():
    """In-memory DB with schema applied."""
    database = Database(":memory:")
    migrate(database)
    yield database
    database.close()
```

- [ ] **Step 5.2: 寫 tests/test_control.py**

```python
import pytest
from db.repos.control import Control


def test_get_returns_seeded_value(db):
    c = Control(db)
    assert c.get("kill_switch") == "false"


def test_get_returns_none_for_missing_key(db):
    c = Control(db)
    assert c.get("does_not_exist") is None


def test_get_bool_parses_seeded_kill_switch(db):
    c = Control(db)
    assert c.get_bool("kill_switch", default=True) is False


def test_get_bool_uses_default_for_missing(db):
    c = Control(db)
    assert c.get_bool("does_not_exist", default=True) is True


def test_get_int(db):
    c = Control(db)
    assert c.get_int("max_open_positions", default=999) == 3


def test_get_float(db):
    c = Control(db)
    assert c.get_float("slippage_max_pct", default=0.0) == 0.01


def test_set_inserts_new_key(db):
    c = Control(db)
    c.set("new_key", "hello")
    assert c.get("new_key") == "hello"


def test_set_overwrites_existing(db):
    c = Control(db)
    c.set("kill_switch", "true")
    assert c.get_bool("kill_switch", default=False) is True
```

- [ ] **Step 5.3: 跑測試,確認 fail**

```bash
pytest tests/test_control.py -v
```

Expected: ModuleNotFoundError for `db.repos.control`

- [ ] **Step 5.4: 寫 db/repos/control.py**

```python
"""Typed key/value access to the `control` table."""
from datetime import datetime, timezone
from typing import Optional
from db.client import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Control:
    def __init__(self, db: Database):
        self._db = db

    def get(self, key: str) -> Optional[str]:
        row = self._db.query_one("SELECT value FROM control WHERE key = ?", (key,))
        return row[0] if row else None

    def get_bool(self, key: str, default: bool) -> bool:
        v = self.get(key)
        if v is None:
            return default
        return v.strip().lower() in ("true", "1", "yes", "on")

    def get_int(self, key: str, default: int) -> int:
        v = self.get(key)
        if v is None:
            return default
        return int(v)

    def get_float(self, key: str, default: float) -> float:
        v = self.get(key)
        if v is None:
            return default
        return float(v)

    def set(self, key: str, value: str) -> None:
        self._db.execute(
            "INSERT INTO control (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, value, _now()),
        )
```

- [ ] **Step 5.5: 跑測試**

```bash
pytest tests/test_control.py -v
```

Expected: 8 passed.

- [ ] **Step 5.6: Commit**

```bash
git add db/repos/control.py tests/conftest.py tests/test_control.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): add Control repo with typed getters

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Strategies Repository

**Files:**
- Create: `db/repos/strategies.py`
- Create: `tests/test_strategies.py`

- [ ] **Step 6.1: 寫 tests/test_strategies.py**

```python
import json
from db.repos.strategies import Strategies, Strategy


def test_insert_and_get_by_name(db):
    s = Strategies(db)
    sid = s.insert(name="trend_majors", params={"universe": ["BTCUSDT", "ETHUSDT"]})
    assert sid > 0
    got = s.get_by_name("trend_majors")
    assert got is not None
    assert got.id == sid
    assert got.name == "trend_majors"
    assert got.params == {"universe": ["BTCUSDT", "ETHUSDT"]}
    assert got.active is True


def test_get_by_name_missing_returns_none(db):
    s = Strategies(db)
    assert s.get_by_name("nope") is None


def test_list_active(db):
    s = Strategies(db)
    s.insert(name="a", params={"x": 1})
    s.insert(name="b", params={"y": 2})
    s.set_active("b", False)
    active = s.list_active()
    names = [st.name for st in active]
    assert names == ["a"]
```

- [ ] **Step 6.2: 寫 db/repos/strategies.py**

```python
"""Strategy registry."""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from db.client import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Strategy:
    id: int
    name: str
    params: dict
    active: bool
    updated_at: str


class Strategies:
    def __init__(self, db: Database):
        self._db = db

    def insert(self, name: str, params: dict, active: bool = True) -> int:
        return self._db.execute(
            "INSERT INTO strategies (name, params_json, active, updated_at) VALUES (?, ?, ?, ?)",
            (name, json.dumps(params), 1 if active else 0, _now()),
        )

    def get_by_name(self, name: str) -> Optional[Strategy]:
        row = self._db.query_one(
            "SELECT id, name, params_json, active, updated_at FROM strategies WHERE name = ?",
            (name,),
        )
        if not row:
            return None
        return Strategy(
            id=row[0],
            name=row[1],
            params=json.loads(row[2]),
            active=bool(row[3]),
            updated_at=row[4],
        )

    def list_active(self) -> List[Strategy]:
        rows = self._db.query(
            "SELECT id, name, params_json, active, updated_at FROM strategies "
            "WHERE active = 1 ORDER BY id"
        )
        return [
            Strategy(
                id=r[0], name=r[1], params=json.loads(r[2]),
                active=bool(r[3]), updated_at=r[4],
            )
            for r in rows
        ]

    def set_active(self, name: str, active: bool) -> None:
        self._db.execute(
            "UPDATE strategies SET active = ?, updated_at = ? WHERE name = ?",
            (1 if active else 0, _now(), name),
        )
```

- [ ] **Step 6.3: 跑測試**

```bash
pytest tests/test_strategies.py -v
```

Expected: 3 passed.

- [ ] **Step 6.4: Commit**

```bash
git add db/repos/strategies.py tests/test_strategies.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): add Strategies repo

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Signals Repository

**Files:**
- Create: `db/repos/signals.py`
- Create: `tests/test_signals.py`

- [ ] **Step 7.1: 寫 tests/test_signals.py**

```python
from datetime import datetime, timedelta, timezone
from db.repos.signals import Signals, Signal
from db.repos.strategies import Strategies


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _future_iso(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _past_iso(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def test_insert_and_list_active(db):
    st = Strategies(db)
    sid = st.insert(name="s1", params={})
    sig = Signals(db)
    signal_id = sig.insert(
        strategy_id=sid, symbol="BTCUSDT", side="long",
        entry_price=60000.0, stop_price=58000.0, target_price=65000.0,
        size_usdt=500.0, expires_at=_future_iso(24), reason="test",
    )
    assert signal_id > 0
    active = sig.list_active()
    assert len(active) == 1
    assert active[0].symbol == "BTCUSDT"
    assert active[0].status == "pending"


def test_list_active_excludes_expired(db):
    st = Strategies(db)
    sid = st.insert(name="s1", params={})
    sig = Signals(db)
    sig.insert(
        strategy_id=sid, symbol="BTC", side="long", entry_price=None,
        stop_price=None, target_price=None, size_usdt=100.0,
        expires_at=_past_iso(1), reason="old",
    )
    assert sig.list_active() == []


def test_list_active_excludes_non_pending(db):
    st = Strategies(db)
    sid = st.insert(name="s1", params={})
    sig = Signals(db)
    s1 = sig.insert(
        strategy_id=sid, symbol="BTC", side="long", entry_price=None,
        stop_price=None, target_price=None, size_usdt=100.0,
        expires_at=_future_iso(24), reason="",
    )
    sig.mark_triggered(s1)
    assert sig.list_active() == []


def test_mark_triggered_sets_status(db):
    st = Strategies(db)
    sid = st.insert(name="s1", params={})
    sig = Signals(db)
    s1 = sig.insert(
        strategy_id=sid, symbol="BTC", side="long", entry_price=None,
        stop_price=None, target_price=None, size_usdt=100.0,
        expires_at=_future_iso(24), reason="",
    )
    sig.mark_triggered(s1)
    assert sig.get(s1).status == "triggered"
```

- [ ] **Step 7.2: 寫 db/repos/signals.py**

```python
"""Signal CRUD."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from db.client import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Signal:
    id: int
    strategy_id: int
    symbol: str
    side: str
    entry_price: Optional[float]
    stop_price: Optional[float]
    target_price: Optional[float]
    size_usdt: float
    status: str
    reason: Optional[str]
    expires_at: Optional[str]
    created_at: str


def _row_to_signal(r) -> Signal:
    return Signal(
        id=r[0], strategy_id=r[1], symbol=r[2], side=r[3],
        entry_price=r[4], stop_price=r[5], target_price=r[6],
        size_usdt=r[7], status=r[8], reason=r[9],
        expires_at=r[10], created_at=r[11],
    )


_COLS = "id, strategy_id, symbol, side, entry_price, stop_price, target_price, size_usdt, status, reason, expires_at, created_at"


class Signals:
    def __init__(self, db: Database):
        self._db = db

    def insert(self, *, strategy_id: int, symbol: str, side: str,
               entry_price: Optional[float], stop_price: Optional[float],
               target_price: Optional[float], size_usdt: float,
               expires_at: Optional[str], reason: Optional[str]) -> int:
        return self._db.execute(
            "INSERT INTO signals (strategy_id, symbol, side, entry_price, stop_price, "
            "target_price, size_usdt, status, reason, expires_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
            (strategy_id, symbol, side, entry_price, stop_price,
             target_price, size_usdt, reason, expires_at, _now()),
        )

    def get(self, signal_id: int) -> Optional[Signal]:
        row = self._db.query_one(
            f"SELECT {_COLS} FROM signals WHERE id = ?", (signal_id,))
        return _row_to_signal(row) if row else None

    def list_active(self) -> List[Signal]:
        rows = self._db.query(
            f"SELECT {_COLS} FROM signals "
            "WHERE status = 'pending' AND (expires_at IS NULL OR expires_at > ?)",
            (_now(),),
        )
        return [_row_to_signal(r) for r in rows]

    def mark_triggered(self, signal_id: int) -> None:
        self._db.execute(
            "UPDATE signals SET status = 'triggered' WHERE id = ?",
            (signal_id,),
        )

    def mark_status(self, signal_id: int, status: str) -> None:
        self._db.execute(
            "UPDATE signals SET status = ? WHERE id = ?",
            (status, signal_id),
        )
```

- [ ] **Step 7.3: 跑測試**

```bash
pytest tests/test_signals.py -v
```

Expected: 4 passed.

- [ ] **Step 7.4: Commit**

```bash
git add db/repos/signals.py tests/test_signals.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): add Signals repo (insert/list_active/mark_*)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Orders Repository

**Files:**
- Create: `db/repos/orders.py`
- Create: `tests/test_orders.py`

- [ ] **Step 8.1: 寫 tests/test_orders.py**

```python
from db.repos.orders import Orders, Order


def test_insert_and_get(db):
    o = Orders(db)
    oid = o.insert(
        signal_id=None, exchange_order_id="ex-1",
        symbol="BTCUSDT", side="buy", qty=0.01, price=60000.0,
        type="market", status="new",
    )
    assert oid > 0
    got = o.get(oid)
    assert got.symbol == "BTCUSDT"
    assert got.fill_qty == 0.0
    assert got.status == "new"


def test_update_fill_marks_filled(db):
    o = Orders(db)
    oid = o.insert(
        signal_id=None, exchange_order_id="ex-1",
        symbol="BTC", side="buy", qty=0.01, price=None,
        type="market", status="new",
    )
    o.update_fill(oid, fill_qty=0.01, fill_price=60100.0, fee_usdt=0.6, status="filled")
    got = o.get(oid)
    assert got.status == "filled"
    assert got.fill_qty == 0.01
    assert got.fill_price == 60100.0
    assert got.fee_usdt == 0.6
    assert got.filled_at is not None
```

- [ ] **Step 8.2: 寫 db/repos/orders.py**

```python
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from db.client import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Order:
    id: int
    signal_id: Optional[int]
    exchange_order_id: Optional[str]
    symbol: str
    side: str
    qty: float
    price: Optional[float]
    type: str
    status: str
    fill_qty: float
    fill_price: Optional[float]
    fee_usdt: float
    created_at: str
    filled_at: Optional[str]


_COLS = "id, signal_id, exchange_order_id, symbol, side, qty, price, type, status, fill_qty, fill_price, fee_usdt, created_at, filled_at"


def _row_to_order(r) -> Order:
    return Order(
        id=r[0], signal_id=r[1], exchange_order_id=r[2], symbol=r[3],
        side=r[4], qty=r[5], price=r[6], type=r[7], status=r[8],
        fill_qty=r[9] or 0.0, fill_price=r[10], fee_usdt=r[11] or 0.0,
        created_at=r[12], filled_at=r[13],
    )


class Orders:
    def __init__(self, db: Database):
        self._db = db

    def insert(self, *, signal_id, exchange_order_id, symbol, side, qty, price, type, status) -> int:
        return self._db.execute(
            "INSERT INTO orders (signal_id, exchange_order_id, symbol, side, qty, price, type, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (signal_id, exchange_order_id, symbol, side, qty, price, type, status, _now()),
        )

    def get(self, order_id: int) -> Optional[Order]:
        row = self._db.query_one(f"SELECT {_COLS} FROM orders WHERE id = ?", (order_id,))
        return _row_to_order(row) if row else None

    def update_fill(self, order_id: int, *, fill_qty, fill_price, fee_usdt, status) -> None:
        self._db.execute(
            "UPDATE orders SET fill_qty = ?, fill_price = ?, fee_usdt = ?, status = ?, filled_at = ? WHERE id = ?",
            (fill_qty, fill_price, fee_usdt, status, _now(), order_id),
        )
```

- [ ] **Step 8.3: 跑測試 + Commit**

```bash
pytest tests/test_orders.py -v
git add db/repos/orders.py tests/test_orders.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): add Orders repo"
```

Expected: 2 passed.

---

## Task 9: Positions Repository

**Files:**
- Create: `db/repos/positions.py`
- Create: `tests/test_positions.py`

- [ ] **Step 9.1: 寫 tests/test_positions.py**

```python
from db.repos.positions import Positions


def test_upsert_inserts_new(db):
    p = Positions(db)
    p.upsert("BTCUSDT", qty=0.01, avg_entry=60000.0)
    got = p.get("BTCUSDT")
    assert got is not None
    assert got.qty == 0.01
    assert got.avg_entry == 60000.0


def test_upsert_overwrites_existing(db):
    p = Positions(db)
    p.upsert("BTC", qty=0.01, avg_entry=60000.0)
    p.upsert("BTC", qty=0.02, avg_entry=61000.0)
    got = p.get("BTC")
    assert got.qty == 0.02
    assert got.avg_entry == 61000.0


def test_list_all_returns_all_symbols(db):
    p = Positions(db)
    p.upsert("BTC", qty=0.01, avg_entry=60000.0)
    p.upsert("ETH", qty=0.5, avg_entry=3000.0)
    syms = {pos.symbol for pos in p.list_all()}
    assert syms == {"BTC", "ETH"}


def test_count_open(db):
    p = Positions(db)
    assert p.count_open() == 0
    p.upsert("BTC", qty=0.01, avg_entry=60000.0)
    p.upsert("ETH", qty=0.5, avg_entry=3000.0)
    assert p.count_open() == 2


def test_get_qty_for_symbol(db):
    p = Positions(db)
    assert p.get_qty("BTC") == 0.0
    p.upsert("BTC", qty=0.01, avg_entry=60000.0)
    assert p.get_qty("BTC") == 0.01


def test_delete_closes_position(db):
    p = Positions(db)
    p.upsert("BTC", qty=0.01, avg_entry=60000.0)
    p.delete("BTC")
    assert p.get("BTC") is None
    assert p.count_open() == 0
```

- [ ] **Step 9.2: 寫 db/repos/positions.py**

```python
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from db.client import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Position:
    symbol: str
    qty: float
    avg_entry: float
    current_price: Optional[float]
    unrealized_pnl: Optional[float]
    updated_at: str


_COLS = "symbol, qty, avg_entry, current_price, unrealized_pnl, updated_at"


def _row_to_position(r) -> Position:
    return Position(
        symbol=r[0], qty=r[1], avg_entry=r[2],
        current_price=r[3], unrealized_pnl=r[4], updated_at=r[5],
    )


class Positions:
    def __init__(self, db: Database):
        self._db = db

    def upsert(self, symbol: str, qty: float, avg_entry: float,
               current_price: Optional[float] = None) -> None:
        unrealized = None
        if current_price is not None:
            unrealized = (current_price - avg_entry) * qty
        self._db.execute(
            "INSERT INTO positions (symbol, qty, avg_entry, current_price, unrealized_pnl, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(symbol) DO UPDATE SET qty = excluded.qty, "
            "avg_entry = excluded.avg_entry, current_price = excluded.current_price, "
            "unrealized_pnl = excluded.unrealized_pnl, updated_at = excluded.updated_at",
            (symbol, qty, avg_entry, current_price, unrealized, _now()),
        )

    def get(self, symbol: str) -> Optional[Position]:
        row = self._db.query_one(f"SELECT {_COLS} FROM positions WHERE symbol = ?", (symbol,))
        return _row_to_position(row) if row else None

    def list_all(self) -> List[Position]:
        rows = self._db.query(f"SELECT {_COLS} FROM positions ORDER BY symbol")
        return [_row_to_position(r) for r in rows]

    def count_open(self) -> int:
        row = self._db.query_one("SELECT COUNT(*) FROM positions WHERE qty != 0")
        return row[0] if row else 0

    def get_qty(self, symbol: str) -> float:
        pos = self.get(symbol)
        return pos.qty if pos else 0.0

    def delete(self, symbol: str) -> None:
        self._db.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
```

- [ ] **Step 9.3: 跑測試 + Commit**

```bash
pytest tests/test_positions.py -v
git add db/repos/positions.py tests/test_positions.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): add Positions repo"
```

Expected: 6 passed.

---

## Task 10: Events Repository

**Files:**
- Create: `db/repos/events.py`
- Create: `tests/test_events.py`

- [ ] **Step 10.1: 寫 tests/test_events.py**

```python
import json
from db.repos.events import Events


def test_log_inserts_event(db):
    e = Events(db)
    e.log("signal_in", {"symbol": "BTC", "size": 500})
    rows = db.query("SELECT type, payload_json FROM events")
    assert len(rows) == 1
    assert rows[0][0] == "signal_in"
    assert json.loads(rows[0][1]) == {"symbol": "BTC", "size": 500}


def test_recent_returns_latest_first(db):
    e = Events(db)
    e.log("a", {})
    e.log("b", {})
    e.log("c", {})
    types = [ev.type for ev in e.recent(limit=2)]
    assert types == ["c", "b"]


def test_count_since_filters_by_time(db):
    e = Events(db)
    e.log("error", {})
    e.log("ok", {})
    e.log("error", {})
    assert e.count_since("error", "2000-01-01T00:00:00+00:00") == 2
```

- [ ] **Step 10.2: 寫 db/repos/events.py**

```python
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List
from db.client import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Event:
    id: int
    type: str
    payload: dict
    created_at: str


class Events:
    def __init__(self, db: Database):
        self._db = db

    def log(self, type: str, payload: dict) -> int:
        return self._db.execute(
            "INSERT INTO events (type, payload_json, created_at) VALUES (?, ?, ?)",
            (type, json.dumps(payload), _now()),
        )

    def recent(self, limit: int = 50) -> List[Event]:
        rows = self._db.query(
            "SELECT id, type, payload_json, created_at FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [Event(id=r[0], type=r[1], payload=json.loads(r[2]), created_at=r[3])
                for r in rows]

    def count_since(self, type: str, since_iso: str) -> int:
        row = self._db.query_one(
            "SELECT COUNT(*) FROM events WHERE type = ? AND created_at >= ?",
            (type, since_iso),
        )
        return row[0] if row else 0
```

- [ ] **Step 10.3: 跑測試 + Commit**

```bash
pytest tests/test_events.py -v
git add db/repos/events.py tests/test_events.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): add Events repo"
```

Expected: 3 passed.

---

## Task 11: Exchange Protocol + ExchangeOrder

**Files:**
- Create: `adapters/exchanges/base.py`

- [ ] **Step 11.1: 寫 adapters/exchanges/base.py**

定義 Protocol + dataclass。沒有單獨測試,因為這只是介面;Task 12 的 fake exchange 測試會驗證契約。

```python
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class ExchangeOrder:
    id: str                   # exchange order id
    status: str               # new / partial / filled / cancelled / failed
    fill_qty: float
    fill_price: Optional[float]
    fee_usdt: float


class Exchange(Protocol):
    """Abstract trading interface.

    P0 只用 _fake.py 實作;P1 加 binance.py。
    """

    def get_price(self, symbol: str) -> float:
        """Return latest mid price for symbol. Raises on unknown symbol."""

    def place_order(self, symbol: str, side: str, qty: float,
                    price: Optional[float] = None, type: str = "market") -> ExchangeOrder:
        """Place an order.

        side: 'buy' or 'sell'
        type: 'market' or 'limit' (P0 only uses market)
        Returns: ExchangeOrder with exchange-assigned id and current status.
        """

    def cancel(self, exchange_order_id: str) -> bool:
        """Cancel an open order. Returns True on success, False if not found / already filled."""
```

- [ ] **Step 11.2: 驗證 import 跟 commit**

```bash
python -c "from adapters.exchanges.base import Exchange, ExchangeOrder; print('OK')"
git add adapters/exchanges/base.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): define Exchange Protocol + ExchangeOrder dataclass"
```

Expected: `OK`.

---

## Task 12: Fake Exchange

**Files:**
- Create: `adapters/exchanges/_fake.py`
- Create: `tests/test_fake_exchange.py`

- [ ] **Step 12.1: 寫 tests/test_fake_exchange.py**

```python
import pytest
from adapters.exchanges._fake import FakeExchange


def test_get_price_returns_set_value():
    ex = FakeExchange()
    ex.set_price("BTCUSDT", 60000.0)
    assert ex.get_price("BTCUSDT") == 60000.0


def test_get_price_unknown_symbol_raises():
    ex = FakeExchange()
    with pytest.raises(KeyError):
        ex.get_price("UNKNOWN")


def test_market_buy_fills_at_current_price():
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    order = ex.place_order("BTC", "buy", qty=0.01, type="market")
    assert order.status == "filled"
    assert order.fill_qty == 0.01
    assert order.fill_price == 60000.0
    assert order.id.startswith("fake-")
    assert order.fee_usdt > 0  # 預設費率 > 0


def test_market_sell_fills_at_current_price():
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    order = ex.place_order("BTC", "sell", qty=0.01, type="market")
    assert order.status == "filled"
    assert order.fill_qty == 0.01


def test_orders_have_unique_ids():
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    a = ex.place_order("BTC", "buy", qty=0.01)
    b = ex.place_order("BTC", "buy", qty=0.01)
    assert a.id != b.id


def test_cancel_returns_false_for_unknown():
    ex = FakeExchange()
    assert ex.cancel("nope") is False


def test_set_failure_makes_next_order_fail():
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    ex.fail_next_n_orders(1)
    order = ex.place_order("BTC", "buy", qty=0.01)
    assert order.status == "failed"
    # 失敗扣完了,下一單恢復
    order2 = ex.place_order("BTC", "buy", qty=0.01)
    assert order2.status == "filled"
```

- [ ] **Step 12.2: 寫 adapters/exchanges/_fake.py**

```python
import itertools
from typing import Dict, Optional
from adapters.exchanges.base import ExchangeOrder


class FakeExchange:
    """In-memory exchange for tests / dev runs.

    Usage:
        ex = FakeExchange()
        ex.set_price("BTC", 60000.0)
        order = ex.place_order("BTC", "buy", qty=0.01)
    """

    DEFAULT_FEE_RATE = 0.001  # 0.1%

    def __init__(self, fee_rate: float = DEFAULT_FEE_RATE):
        self._prices: Dict[str, float] = {}
        self._fee_rate = fee_rate
        self._id_seq = itertools.count(1)
        self._fail_remaining = 0

    # --- test hooks ---
    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price

    def fail_next_n_orders(self, n: int) -> None:
        self._fail_remaining = n

    # --- Exchange protocol ---
    def get_price(self, symbol: str) -> float:
        if symbol not in self._prices:
            raise KeyError(f"unknown symbol: {symbol}")
        return self._prices[symbol]

    def place_order(self, symbol: str, side: str, qty: float,
                    price: Optional[float] = None, type: str = "market") -> ExchangeOrder:
        oid = f"fake-{next(self._id_seq)}"
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            return ExchangeOrder(id=oid, status="failed", fill_qty=0.0,
                                 fill_price=None, fee_usdt=0.0)
        fill_price = self.get_price(symbol) if type == "market" else (price or 0.0)
        fee = abs(qty * fill_price * self._fee_rate)
        return ExchangeOrder(id=oid, status="filled", fill_qty=qty,
                             fill_price=fill_price, fee_usdt=fee)

    def cancel(self, exchange_order_id: str) -> bool:
        # P0 fake 全部 market order 都當下成交,沒 open order 可 cancel
        return False
```

- [ ] **Step 12.3: 跑測試 + Commit**

```bash
pytest tests/test_fake_exchange.py -v
git add adapters/exchanges/_fake.py tests/test_fake_exchange.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): add in-memory FakeExchange with price + failure hooks"
```

Expected: 7 passed.

---

## Task 13: Matcher (signal trigger 判斷)

**Files:**
- Create: `executor/matcher.py`
- Create: `tests/test_matcher.py`

P0 規則(spec 第 7 節隱含):
- Signal side=long + entry_price 為 None → 立刻觸發(market entry)
- Signal side=long + entry_price 有值 → 當 current_price >= entry_price 時觸發(向上突破)
- Signal side=flat → 持倉時觸發(平倉信號;P0 e2e 不一定會走到,但接口先留)
- Slippage 檢查留給 circuit breaker,matcher 只負責「規則上是否該觸發」

- [ ] **Step 13.1: 寫 tests/test_matcher.py**

```python
from db.repos.signals import Signal
from executor.matcher import should_trigger


def _signal(side="long", entry=None):
    return Signal(
        id=1, strategy_id=1, symbol="BTC", side=side,
        entry_price=entry, stop_price=None, target_price=None,
        size_usdt=500.0, status="pending", reason="",
        expires_at=None, created_at="2026-05-30T00:00:00+00:00",
    )


def test_market_long_always_triggers():
    sig = _signal(side="long", entry=None)
    assert should_trigger(sig, current_price=60000.0) is True


def test_long_above_entry_triggers():
    sig = _signal(side="long", entry=60000.0)
    assert should_trigger(sig, current_price=60001.0) is True


def test_long_at_entry_triggers():
    sig = _signal(side="long", entry=60000.0)
    assert should_trigger(sig, current_price=60000.0) is True


def test_long_below_entry_does_not_trigger():
    sig = _signal(side="long", entry=60000.0)
    assert should_trigger(sig, current_price=59999.0) is False


def test_flat_signal_triggers_when_holding():
    sig = _signal(side="flat", entry=None)
    assert should_trigger(sig, current_price=60000.0, holding_qty=0.01) is True


def test_flat_signal_does_not_trigger_when_no_holding():
    sig = _signal(side="flat", entry=None)
    assert should_trigger(sig, current_price=60000.0, holding_qty=0.0) is False
```

- [ ] **Step 13.2: 寫 executor/matcher.py**

```python
from db.repos.signals import Signal


def should_trigger(signal: Signal, current_price: float, holding_qty: float = 0.0) -> bool:
    if signal.side == "long":
        if signal.entry_price is None:
            return True
        return current_price >= signal.entry_price
    if signal.side == "flat":
        return holding_qty > 0
    return False
```

- [ ] **Step 13.3: 跑測試 + Commit**

```bash
pytest tests/test_matcher.py -v
git add executor/matcher.py tests/test_matcher.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): add matcher for signal trigger decisions"
```

Expected: 6 passed.

---

## Task 14: Circuit Breaker

**Files:**
- Create: `executor/circuit_breaker.py`
- Create: `tests/test_circuit_breaker.py`

設計:`CircuitBreaker` 接受 `Control`、`Positions`、`Events` 三個 repo。對外:
- `evaluate_new_entry(symbol, size_usdt, universe, daily_realized_pnl)` → `Optional[str]`(None=可下,字串=拒絕原因)
- `evaluate_risk_reduction()` → 永遠 None
- `check_slippage(estimated_pct)` → `Optional[str]`
- `note_api_failure(symbol)`、`note_api_success(symbol)`、`should_circuit_open(symbol)`

- [ ] **Step 14.1: 寫 tests/test_circuit_breaker.py**

```python
import pytest
from db.repos.control import Control
from db.repos.positions import Positions
from db.repos.events import Events
from executor.circuit_breaker import CircuitBreaker


@pytest.fixture(autouse=True)
def _reset_api_failures():
    # CircuitBreaker._api_failures 是 class state,測試間清掉
    CircuitBreaker._api_failures = None
    yield


@pytest.fixture
def cb(db):
    return CircuitBreaker(Control(db), Positions(db), Events(db))


def test_default_allows_entry(db, cb):
    assert cb.evaluate_new_entry(
        symbol="BTCUSDT", size_usdt=500.0,
        universe=["BTCUSDT"], daily_realized_pnl=0.0,
    ) is None


def test_kill_switch_blocks_entry(db, cb):
    Control(db).set("kill_switch", "true")
    reason = cb.evaluate_new_entry(
        symbol="BTCUSDT", size_usdt=500.0,
        universe=["BTCUSDT"], daily_realized_pnl=0.0,
    )
    assert reason is not None and "kill_switch" in reason.lower()


def test_size_above_cap_blocks(db, cb):
    reason = cb.evaluate_new_entry(
        symbol="BTC", size_usdt=501.0,
        universe=["BTC"], daily_realized_pnl=0.0,
    )
    assert reason is not None and "max_per_trade" in reason.lower()


def test_symbol_not_in_universe_blocks(db, cb):
    reason = cb.evaluate_new_entry(
        symbol="DOGE", size_usdt=100.0,
        universe=["BTC", "ETH"], daily_realized_pnl=0.0,
    )
    assert reason is not None and "universe" in reason.lower()


def test_daily_loss_breach_blocks_and_sets_kill_switch(db, cb):
    reason = cb.evaluate_new_entry(
        symbol="BTC", size_usdt=100.0,
        universe=["BTC"], daily_realized_pnl=-300.01,
    )
    assert reason is not None and "daily_loss" in reason.lower()
    assert Control(db).get_bool("kill_switch", default=False) is True


def test_max_open_positions_blocks(db, cb):
    Positions(db).upsert("BTC", qty=0.01, avg_entry=60000.0)
    Positions(db).upsert("ETH", qty=0.5, avg_entry=3000.0)
    Positions(db).upsert("SOL", qty=10, avg_entry=150.0)
    reason = cb.evaluate_new_entry(
        symbol="ADA", size_usdt=100.0,
        universe=["BTC", "ETH", "SOL", "ADA"], daily_realized_pnl=0.0,
    )
    assert reason is not None and "max_open_positions" in reason.lower()


def test_per_symbol_cap_blocks_adding(db, cb):
    Positions(db).upsert("BTC", qty=0.01, avg_entry=60000.0)
    reason = cb.evaluate_new_entry(
        symbol="BTC", size_usdt=100.0,
        universe=["BTC"], daily_realized_pnl=0.0,
    )
    assert reason is not None
    low = reason.lower()
    assert "per_symbol" in low or "position_per_symbol" in low


def test_slippage_above_cap_blocks(db, cb):
    assert cb.check_slippage(0.011) is not None
    assert cb.check_slippage(0.009) is None


def test_risk_reduction_always_allowed(db, cb):
    Control(db).set("kill_switch", "true")
    assert cb.evaluate_risk_reduction() is None


def test_api_failure_circuit(db, cb):
    assert cb.should_circuit_open("BTC") is False
    cb.note_api_failure("BTC")
    cb.note_api_failure("BTC")
    assert cb.should_circuit_open("BTC") is False
    cb.note_api_failure("BTC")
    assert cb.should_circuit_open("BTC") is True
```

- [ ] **Step 14.2: 寫 executor/circuit_breaker.py**

```python
from typing import List, Optional
from db.repos.control import Control
from db.repos.positions import Positions
from db.repos.events import Events


class CircuitBreaker:
    # Class-level state (P0 single-process executor is fine; P1 move to events table)
    _api_failures = None

    def __init__(self, control: Control, positions: Positions, events: Events):
        self._c = control
        self._p = positions
        self._e = events

    def evaluate_new_entry(self, *, symbol: str, size_usdt: float,
                           universe: List[str], daily_realized_pnl: float) -> Optional[str]:
        # 1. universe 白名單(不能繞過)
        if symbol not in universe:
            return f"universe: {symbol} not in whitelist"

        # 2. kill switch
        if self._c.get_bool("kill_switch", default=False):
            return "kill_switch: enabled"

        # 3. 每日虧損上限 → 自動觸發 kill switch
        max_daily_loss = self._c.get_float("max_daily_loss_usdt", default=300.0)
        if daily_realized_pnl <= -max_daily_loss:
            self._c.set("kill_switch", "true")
            self._e.log("circuit_open", {
                "reason": "daily_loss",
                "daily_realized_pnl": daily_realized_pnl,
                "cap": max_daily_loss,
            })
            return f"daily_loss: realized {daily_realized_pnl:.2f} <= -{max_daily_loss:.2f}"

        # 4. 單筆上限
        max_per_trade = self._c.get_float("max_per_trade_usdt", default=500.0)
        if size_usdt > max_per_trade:
            return f"max_per_trade: {size_usdt:.2f} > {max_per_trade:.2f}"

        # 5. 同時持倉上限
        max_open = self._c.get_int("max_open_positions", default=3)
        existing_count = self._p.count_open()
        already_have_this = self._p.get_qty(symbol) > 0
        if not already_have_this and existing_count >= max_open:
            return f"max_open_positions: already {existing_count} >= {max_open}"

        # 6. 單一 symbol 持倉上限
        max_per_symbol = self._c.get_int("max_position_per_symbol", default=1)
        if already_have_this and max_per_symbol <= 1:
            return f"max_position_per_symbol: {symbol} already held"

        return None

    def check_slippage(self, estimated_pct: float) -> Optional[str]:
        cap = self._c.get_float("slippage_max_pct", default=0.01)
        if estimated_pct > cap:
            return f"slippage: {estimated_pct:.4f} > {cap:.4f}"
        return None

    def evaluate_risk_reduction(self) -> Optional[str]:
        return None  # 風險縮減動作永遠允許(spec 第 8 節核心原則 #2)

    def note_api_failure(self, symbol: str) -> None:
        if CircuitBreaker._api_failures is None:
            CircuitBreaker._api_failures = {}
        CircuitBreaker._api_failures[symbol] = CircuitBreaker._api_failures.get(symbol, 0) + 1

    def note_api_success(self, symbol: str) -> None:
        if CircuitBreaker._api_failures is None:
            return
        CircuitBreaker._api_failures.pop(symbol, None)

    def should_circuit_open(self, symbol: str) -> bool:
        threshold = self._c.get_int("api_fail_threshold", default=3)
        count = (CircuitBreaker._api_failures or {}).get(symbol, 0)
        return count >= threshold
```

- [ ] **Step 14.3: 跑測試 + Commit**

```bash
pytest tests/test_circuit_breaker.py -v
git add executor/circuit_breaker.py tests/test_circuit_breaker.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): add CircuitBreaker (kill switch + caps + slippage + api fail)"
```

Expected: 10 passed。

---

## Task 15: Tick Orchestrator + CLI Entry

**Files:**
- Create: `executor/tick.py`
- Create: `tests/test_tick.py`(整合 fake exchange 做小測試,大型 e2e 留 Task 16)

設計 `run_tick(db, exchange, strategy_name="trend_majors")`:
1. 抓 strategy.params.universe(P0 測試會手動 insert strategy)
2. 抓 active signals
3. 對每個 signal:
   - 不在 universe → skip(寫 event)
   - 抓現價(失敗 → note_api_failure → skip;成功 → note_api_success)
   - should_trigger? 否則 skip
   - circuit_breaker.evaluate_new_entry → 拒絕原因 → skip(寫 event)
   - place_order → 失敗 → note_api_failure → skip(寫 event)
   - 寫 Orders.insert + update_fill;Positions.upsert(對 buy);Signals.mark_triggered;寫 event

P0 不做 stop/target 觸發、不做 flat 平倉、不算 daily P&L(都先傳 0)。這些 P2 處理。

- [ ] **Step 15.1: 寫 tests/test_tick.py(小規模)**

```python
from datetime import datetime, timedelta, timezone
import pytest
from adapters.exchanges._fake import FakeExchange
from db.repos.control import Control
from db.repos.events import Events
from db.repos.orders import Orders
from db.repos.positions import Positions
from db.repos.signals import Signals
from db.repos.strategies import Strategies
from executor.circuit_breaker import CircuitBreaker
from executor.tick import run_tick


def _future_iso(hours=24):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _setup_strategy(db, universe):
    Strategies(db).insert(name="trend_majors", params={"universe": universe})


def test_market_signal_results_in_order_and_position(db):
    _setup_strategy(db, universe=["BTCUSDT"])
    Signals(db).insert(
        strategy_id=1, symbol="BTCUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=300.0, expires_at=_future_iso(), reason="market entry test",
    )
    ex = FakeExchange()
    ex.set_price("BTCUSDT", 60000.0)

    summary = run_tick(db, ex, strategy_name="trend_majors")

    assert summary["triggered"] == 1
    assert summary["blocked"] == 0
    pos = Positions(db).get("BTCUSDT")
    assert pos is not None
    assert pos.qty == pytest.approx(300.0 / 60000.0)
    assert pos.avg_entry == 60000.0


def test_signal_outside_universe_is_blocked(db):
    _setup_strategy(db, universe=["BTCUSDT"])
    Signals(db).insert(
        strategy_id=1, symbol="DOGEUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    summary = run_tick(db, ex, strategy_name="trend_majors")
    assert summary["triggered"] == 0
    assert summary["blocked"] == 1


def test_kill_switch_blocks_all_entries(db):
    _setup_strategy(db, universe=["BTC"])
    Control(db).set("kill_switch", "true")
    Signals(db).insert(
        strategy_id=1, symbol="BTC", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    summary = run_tick(db, ex, strategy_name="trend_majors")
    assert summary["triggered"] == 0
    assert summary["blocked"] == 1


def test_failed_order_does_not_create_position(db):
    _setup_strategy(db, universe=["BTC"])
    Signals(db).insert(
        strategy_id=1, symbol="BTC", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    ex.fail_next_n_orders(1)
    summary = run_tick(db, ex, strategy_name="trend_majors")
    assert summary["triggered"] == 0
    assert summary["api_errors"] == 1
    assert Positions(db).get("BTC") is None


```

- [ ] **Step 15.2: 寫 executor/tick.py**

```python
"""Main tick loop: read signals → match → check risk → place order → update state.

P0 範圍:
- 進場(market 或 long-side breakout)
- 不做 stop/target/flat 平倉(P2)
- daily_realized_pnl 一律當 0(P3 加 pnl 計算)
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
        # 1. 抓現價
        try:
            current_price = exchange.get_price(sig.symbol)
            cb.note_api_success(sig.symbol)
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

        # 3. circuit breaker(P0:daily_realized_pnl=0)
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

        # 4. 下單(market only in P0)
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

        # 5. 寫回 state
        orders.update_fill(
            order_id, fill_qty=ex_order.fill_qty,
            fill_price=ex_order.fill_price, fee_usdt=ex_order.fee_usdt,
            status="filled",
        )
        positions.upsert(sig.symbol, qty=ex_order.fill_qty,
                         avg_entry=ex_order.fill_price, current_price=current_price)
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
        # 種一筆 strategy + 一筆 signal
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
        # P0 不接 Binance,所以非 --fake 模式直接拒絕
        print("non-fake mode requires Binance adapter (P1).", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 15.3: 跑 unit tests**

```bash
pytest tests/test_tick.py -v
```

Expected: 4 passed.

- [ ] **Step 15.4: 跑 CLI smoke test**

```bash
python -m executor.tick --fake
```

Expected stdout:
```
[fake tick] summary: {'triggered': 1, 'blocked': 0, 'api_errors': 0}
  position: BTCUSDT qty=0.005000 avg_entry=60000.0
```

- [ ] **Step 15.5: Commit**

```bash
git add executor/tick.py tests/test_tick.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p0): add tick orchestrator + CLI smoke test (--fake)"
```

---

## Task 16: E2E Test + 最終驗收

**Files:**
- Create: `tests/test_tick_e2e.py`

整合測試:一條完整的「3 個 signal → 走過 matcher、circuit breaker、fake exchange → 部分通過、部分被擋 → state 與 event log 都符合預期」流程。

- [ ] **Step 16.1: 寫 tests/test_tick_e2e.py**

```python
from datetime import datetime, timedelta, timezone
from adapters.exchanges._fake import FakeExchange
from db.repos.control import Control
from db.repos.events import Events
from db.repos.positions import Positions
from db.repos.signals import Signals
from db.repos.strategies import Strategies
from executor.tick import run_tick


def _future(hours=24):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def test_e2e_mixed_outcomes(db):
    """三筆 signal:
       - BTC market entry → 應該成交
       - ETH 標的不在 universe → 應該被擋
       - SOL price 低於 entry → 應該不觸發(matcher 擋,計入 'untriggered' 而非 'blocked')
    """
    universe = ["BTCUSDT", "SOLUSDT"]
    Strategies(db).insert(name="trend_majors", params={"universe": universe})

    Signals(db).insert(
        strategy_id=1, symbol="BTCUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=300.0, expires_at=_future(), reason="market BTC",
    )
    Signals(db).insert(
        strategy_id=1, symbol="ETHUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=300.0, expires_at=_future(), reason="outside universe",
    )
    Signals(db).insert(
        strategy_id=1, symbol="SOLUSDT", side="long",
        entry_price=200.0, stop_price=180.0, target_price=240.0,
        size_usdt=300.0, expires_at=_future(), reason="needs breakout",
    )

    ex = FakeExchange()
    ex.set_price("BTCUSDT", 60000.0)
    ex.set_price("ETHUSDT", 3000.0)
    ex.set_price("SOLUSDT", 150.0)  # 低於 entry 200

    summary = run_tick(db, ex, strategy_name="trend_majors")

    assert summary["triggered"] == 1
    assert summary["blocked"] == 1
    assert summary["api_errors"] == 0

    # BTC 有部位
    btc = Positions(db).get("BTCUSDT")
    assert btc is not None
    assert btc.qty > 0

    # ETH 沒部位
    assert Positions(db).get("ETHUSDT") is None

    # SOL 沒部位(matcher 沒觸發)
    assert Positions(db).get("SOLUSDT") is None

    # 應有對應 events
    events = Events(db)
    fills = [e for e in events.recent(50) if e.type == "fill"]
    blocks = [e for e in events.recent(50) if e.type == "blocked"]
    assert len(fills) == 1
    assert fills[0].payload["symbol"] == "BTCUSDT"
    assert len(blocks) == 1
    assert blocks[0].payload["symbol"] == "ETHUSDT"
    assert "universe" in blocks[0].payload["reason"].lower()


def test_e2e_kill_switch_after_daily_loss(db):
    universe = ["BTC"]
    Strategies(db).insert(name="trend_majors", params={"universe": universe})
    Signals(db).insert(
        strategy_id=1, symbol="BTC", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future(), reason="",
    )

    # 模擬 daily_realized_pnl ≤ -300 → 直接傳給 run_tick 沒辦法,
    # 改用 manual call CircuitBreaker.evaluate_new_entry 來驗證
    from executor.circuit_breaker import CircuitBreaker
    from db.repos.positions import Positions as PosRepo
    cb = CircuitBreaker(Control(db), PosRepo(db), Events(db))
    reason = cb.evaluate_new_entry(
        symbol="BTC", size_usdt=100.0, universe=universe,
        daily_realized_pnl=-301.0,
    )
    assert reason is not None
    assert Control(db).get_bool("kill_switch", default=False) is True

    # 之後 kill switch 已經被打開 → 即使有正常 fake exchange,signal 還是擋
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    summary = run_tick(db, ex, strategy_name="trend_majors")
    assert summary["triggered"] == 0
    assert summary["blocked"] == 1
```

- [ ] **Step 16.2: 跑整套測試**

```bash
pytest tests/ -v
```

Expected: 全綠(總計大約 50+ tests)。

- [ ] **Step 16.3: 跑 CLI smoke**

```bash
python -m executor.tick --fake
```

Expected:
```
[fake tick] summary: {'triggered': 1, 'blocked': 0, 'api_errors': 0}
  position: BTCUSDT qty=0.005000 avg_entry=60000.0
```

- [ ] **Step 16.4: 最終 Commit**

```bash
git add tests/test_tick_e2e.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "test(p0): add e2e tick test (mixed signal outcomes + kill switch)"
```

- [ ] **Step 16.5: P0 收斂報告(寫到 plan 末尾)**

```bash
git log --oneline | head -20
pytest tests/ --tb=no -q
```

確認:
- ✅ `pytest tests/` 全綠
- ✅ `python -m executor.tick --fake` 印出 1 個 triggered + position
- ✅ git log 有 16+ 次 commit(每個 task 1 個以上)
- ✅ 沒有任何 .env / api key 進 git
- ✅ `state/local.db` 在 .gitignore 內,沒被 commit

---

## P0 Exit Criteria

對應 spec 第 11 節 P0:

| 項目 | 怎麼驗 | 通過 |
|---|---|---|
| repo 結構齊 | `ls adapters db executor schema tests` | — |
| Turso 介面層 | `db/client.py` 已抽象出 url-based 連線 | — |
| schema migrate 跑得通 | `python -c "from schema.migrate import migrate; from db.client import Database; migrate(Database(':memory:'))"` | — |
| fake exchange adapter | `pytest tests/test_fake_exchange.py` 全綠 | — |
| e2e mock 流程跑通 | `pytest tests/test_tick_e2e.py` + `python -m executor.tick --fake` 都有正確輸出 | — |
| 風控 8 條中 6 條可測 | `pytest tests/test_circuit_breaker.py` 全綠(剩下 daily report、Discord 通知留 P3) | — |

## 後續(不在 P0)

- **P1**:`adapters/exchanges/binance.py`、`db/client.py` 加 libsql:// scheme、`.github/workflows/exec_tick.yml`
- **P2**:`pipeline/strategy.py`、`pipeline/scan.py`、Cowork 端 Claude prompt、stop/target 平倉邏輯
- **P3**:`adapters/notify/chat_notify_hub.py`、`reporter.py`、`_START_HERE/*.bat`、daily P&L
- **P4**:testnet 跑滿觀察期

每個都會有自己的 plan,不會塞進這份。
