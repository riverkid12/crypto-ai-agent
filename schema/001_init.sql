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

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
