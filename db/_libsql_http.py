"""Minimal Hrana v3 HTTP client for Turso/libsql.

Why HTTP (not libsql-experimental)? The native SDK requires Rust toolchain
to install on some platforms (Windows+Python 3.14 fails on puccinialin cache).
Since requests is already in our deps and Hrana v3 is a stable JSON protocol,
we just speak HTTP directly.
"""
from typing import Any, Iterable, List, Optional, Tuple

import requests


def _to_value(p: Any) -> dict:
    if p is None:
        return {"type": "null"}
    if isinstance(p, bool):
        # bool is subclass of int — check first
        return {"type": "integer", "value": "1" if p else "0"}
    if isinstance(p, int):
        return {"type": "integer", "value": str(p)}
    if isinstance(p, float):
        return {"type": "float", "value": p}
    if isinstance(p, str):
        return {"type": "text", "value": p}
    if isinstance(p, (bytes, bytearray)):
        import base64
        return {"type": "blob", "base64": base64.b64encode(bytes(p)).decode()}
    raise TypeError(f"unsupported param type for libsql: {type(p).__name__}")


def _from_value(v: dict) -> Any:
    t = v.get("type")
    if t == "null":
        return None
    if t == "integer":
        return int(v["value"])
    if t == "float":
        return float(v["value"])
    if t == "text":
        return v["value"]
    if t == "blob":
        import base64
        return base64.b64decode(v["base64"])
    raise ValueError(f"unknown libsql value type: {t}")


class _Cursor:
    """sqlite3.Cursor-compatible adapter for one execute() result."""

    def __init__(self, result: dict):
        self._rows = [
            tuple(_from_value(v) for v in row)
            for row in result.get("rows", [])
        ]
        last = result.get("last_insert_rowid")
        self.lastrowid: Optional[int] = int(last) if last is not None else None
        self._iter = iter(self._rows)

    def fetchall(self) -> List[Tuple]:
        return list(self._rows)

    def fetchone(self) -> Optional[Tuple]:
        try:
            return next(self._iter)
        except StopIteration:
            return None


class HranaConnection:
    """sqlite3.Connection-compatible adapter over Turso HTTP API."""

    def __init__(self, url: str, auth_token: str, timeout: float = 30.0):
        # url is already converted to https:// by caller
        self._endpoint = url.rstrip("/") + "/v2/pipeline"
        self._token = auth_token
        self._timeout = timeout

    def execute(self, sql: str, params: Iterable[Any] = ()) -> _Cursor:
        return self._execute_single(sql, params)

    def executescript(self, script: str) -> None:
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if stmt:
                self._execute_single(stmt, ())

    def commit(self) -> None:
        # Hrana auto-commits each request; no batched-tx support here.
        return

    def close(self) -> None:
        # Stateless HTTP — nothing to close.
        return

    def _execute_single(self, sql: str, params: Iterable[Any]) -> _Cursor:
        args = [_to_value(p) for p in params]
        body = {
            "requests": [
                {"type": "execute", "stmt": {"sql": sql, "args": args}},
                {"type": "close"},
            ]
        }
        resp = requests.post(
            self._endpoint,
            json=body,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        first = data["results"][0]
        if first.get("type") == "error":
            err = first.get("error", {})
            raise RuntimeError(f"libsql error: {err.get('message', 'unknown')} ({err.get('code', '?')})")
        if first.get("type") != "ok":
            raise RuntimeError(f"libsql unexpected response: {first}")
        result = first["response"]["result"]
        return _Cursor(result)
