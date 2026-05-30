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
