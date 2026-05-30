import pytest
import responses
from db.client import Database, _parse_url


# --- URL parsing ---

def test_parse_memory():
    scheme, target, token = _parse_url(":memory:", auth_token=None)
    assert scheme == "sqlite"
    assert target == ":memory:"
    assert token is None


def test_parse_sqlite_file():
    scheme, target, token = _parse_url("sqlite:///state/local.db", auth_token=None)
    assert scheme == "sqlite"
    assert target == "state/local.db"
    assert token is None


def test_parse_libsql_with_token():
    url = "libsql://my-db-username.turso.io"
    scheme, target, token = _parse_url(url, auth_token="jwt-token-here")
    assert scheme == "libsql"
    assert target == "https://my-db-username.turso.io"  # converted to https
    assert token == "jwt-token-here"


def test_parse_libsql_without_token_raises():
    with pytest.raises(ValueError, match="libsql.*auth_token"):
        _parse_url("libsql://my-db.turso.io", auth_token=None)


def test_parse_unknown_scheme_raises():
    with pytest.raises(ValueError, match="unsupported"):
        _parse_url("postgres://x", auth_token=None)


# --- existing sqlite tests still pass ---

def test_memory_db_still_works():
    db = Database(":memory:")
    db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    db.execute("INSERT INTO t (name) VALUES (?)", ("alice",))
    assert db.query("SELECT id, name FROM t") == [(1, "alice")]
    db.close()


# --- libsql HTTP client (mocked) ---

LIBSQL_URL = "libsql://my-db.turso.io"
HTTP_URL = "https://my-db.turso.io/v2/pipeline"


def _ok_response(execute_result):
    """Build a Hrana response wrapping a single execute result."""
    return {
        "results": [
            {"type": "ok", "response": {"type": "execute", "result": execute_result}},
            {"type": "ok", "response": {"type": "close"}},
        ]
    }


def _empty_result(affected_row_count=0, last_insert_rowid=None):
    r = {"cols": [], "rows": [], "affected_row_count": affected_row_count}
    if last_insert_rowid is not None:
        r["last_insert_rowid"] = str(last_insert_rowid)
    return r


@responses.activate
def test_libsql_execute_sends_pipeline_request():
    responses.add(responses.POST, HTTP_URL, json=_ok_response(_empty_result(last_insert_rowid=1)), status=200)
    db = Database(LIBSQL_URL, auth_token="tok")
    rowid = db.execute("INSERT INTO t (name) VALUES (?)", ("alice",))
    assert rowid == 1
    assert len(responses.calls) == 1
    req = responses.calls[0].request
    assert req.headers["Authorization"] == "Bearer tok"
    import json
    body = json.loads(req.body)
    # Expect: pipeline with execute then close
    assert len(body["requests"]) == 2
    assert body["requests"][0]["type"] == "execute"
    assert body["requests"][0]["stmt"]["sql"].startswith("INSERT INTO t")
    args = body["requests"][0]["stmt"]["args"]
    assert args == [{"type": "text", "value": "alice"}]
    assert body["requests"][1]["type"] == "close"


@responses.activate
def test_libsql_query_returns_rows_as_tuples():
    result = {
        "cols": [{"name": "id"}, {"name": "name"}],
        "rows": [
            [{"type": "integer", "value": "1"}, {"type": "text", "value": "alice"}],
            [{"type": "integer", "value": "2"}, {"type": "text", "value": "bob"}],
        ],
        "affected_row_count": 0,
    }
    responses.add(responses.POST, HTTP_URL, json=_ok_response(result), status=200)
    db = Database(LIBSQL_URL, auth_token="tok")
    rows = db.query("SELECT id, name FROM t")
    assert rows == [(1, "alice"), (2, "bob")]


@responses.activate
def test_libsql_query_one_returns_first_or_none():
    # Empty result
    responses.add(responses.POST, HTTP_URL,
                  json=_ok_response({"cols": [], "rows": [], "affected_row_count": 0}),
                  status=200)
    db = Database(LIBSQL_URL, auth_token="tok")
    assert db.query_one("SELECT 1") is None

    # Single row
    result = {
        "cols": [{"name": "x"}],
        "rows": [[{"type": "float", "value": 3.14}]],
        "affected_row_count": 0,
    }
    responses.add(responses.POST, HTTP_URL, json=_ok_response(result), status=200)
    row = db.query_one("SELECT x FROM t")
    assert row == (3.14,)


@responses.activate
def test_libsql_value_types_roundtrip():
    """null, integer, float, text values are correctly decoded."""
    result = {
        "cols": [{"name": "a"}, {"name": "b"}, {"name": "c"}, {"name": "d"}],
        "rows": [[
            {"type": "null"},
            {"type": "integer", "value": "42"},
            {"type": "float", "value": 1.5},
            {"type": "text", "value": "hello"},
        ]],
        "affected_row_count": 0,
    }
    responses.add(responses.POST, HTTP_URL, json=_ok_response(result), status=200)
    db = Database(LIBSQL_URL, auth_token="tok")
    row = db.query_one("SELECT a, b, c, d FROM t")
    assert row == (None, 42, 1.5, "hello")


@responses.activate
def test_libsql_param_encoding():
    """None, int, float, str, bool params correctly encoded into Hrana args."""
    responses.add(responses.POST, HTTP_URL, json=_ok_response(_empty_result()), status=200)
    db = Database(LIBSQL_URL, auth_token="tok")
    db.execute("INSERT INTO t VALUES (?, ?, ?, ?, ?)", (None, 42, 1.5, "hello", True))
    import json
    body = json.loads(responses.calls[0].request.body)
    args = body["requests"][0]["stmt"]["args"]
    assert args == [
        {"type": "null"},
        {"type": "integer", "value": "42"},
        {"type": "float", "value": 1.5},
        {"type": "text", "value": "hello"},
        {"type": "integer", "value": "1"},  # bool True -> integer 1
    ]


@responses.activate
def test_libsql_executescript_splits_on_semicolons():
    """executescript splits multi-statement SQL on ; and sends each."""
    responses.add(responses.POST, HTTP_URL, json=_ok_response(_empty_result()), status=200)
    responses.add(responses.POST, HTTP_URL, json=_ok_response(_empty_result()), status=200)
    db = Database(LIBSQL_URL, auth_token="tok")
    db.executescript("CREATE TABLE a (id INT); CREATE TABLE b (id INT);")
    assert len(responses.calls) == 2  # two non-empty statements


@responses.activate
def test_libsql_5xx_raises():
    responses.add(responses.POST, HTTP_URL, status=500, body="oops")
    db = Database(LIBSQL_URL, auth_token="tok")
    with pytest.raises(Exception):  # any flavor of HTTPError / requests error
        db.execute("INSERT INTO t VALUES (1)")


@responses.activate
def test_libsql_hrana_error_response_raises():
    """When Hrana response has type=error, raise."""
    responses.add(responses.POST, HTTP_URL, json={
        "results": [
            {"type": "error", "error": {"message": "syntax error", "code": "SQL_PARSE"}}
        ]
    }, status=200)
    db = Database(LIBSQL_URL, auth_token="tok")
    with pytest.raises(Exception, match="syntax error"):
        db.execute("THIS IS NOT SQL")
