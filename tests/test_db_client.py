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
