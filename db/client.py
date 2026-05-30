"""Thin wrapper over sqlite3 / libsql with a connection-string API.

Supported schemes:
- ":memory:"             — in-memory sqlite (tests)
- "sqlite:///path/to.db" — local file sqlite
- "libsql://<host>"      — Turso cloud (requires auth_token kwarg).
                           Uses HTTP API (Hrana v3) — no Rust toolchain needed.
"""
import sqlite3
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple


def _parse_url(url: str, auth_token: Optional[str] = None) -> Tuple[str, str, Optional[str]]:
    """Return (scheme, target, auth_token).

    scheme: "sqlite" or "libsql"
    target: path string for sqlite, https URL for libsql
    auth_token: passed through unchanged for libsql; ignored for sqlite
    """
    if url == ":memory:":
        return ("sqlite", ":memory:", None)
    if url.startswith("sqlite:///"):
        return ("sqlite", url[len("sqlite:///"):], None)
    if url.startswith("sqlite://"):
        return ("sqlite", url[len("sqlite://"):], None)
    if url.startswith("libsql://"):
        if not auth_token:
            raise ValueError(f"libsql requires auth_token (DB url: {url})")
        https_url = "https://" + url[len("libsql://"):]
        return ("libsql", https_url, auth_token)
    raise ValueError(f"unsupported DB url: {url}")


class Database:
    def __init__(self, url: str, auth_token: Optional[str] = None):
        scheme, target, token = _parse_url(url, auth_token)
        if scheme == "sqlite":
            if target != ":memory:":
                Path(target).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(target)
            self._conn.execute("PRAGMA foreign_keys = ON")
        else:  # libsql
            from db._libsql_http import HranaConnection
            self._conn = HranaConnection(target, auth_token=token)

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        cur = self._conn.execute(sql, tuple(params))
        self._conn.commit()
        return cur.lastrowid

    def executescript(self, script: str) -> None:
        if hasattr(self._conn, "executescript"):
            self._conn.executescript(script)
        else:
            for stmt in script.split(";"):
                stmt = stmt.strip()
                if stmt:
                    self._conn.execute(stmt)
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
