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
