"""Tests for the per-user line-preference store."""

import sqlite3

from enfilera.lines import Line
from enfilera.preferences_store import LinePreferenceStore, chosen_line

USER = 7
LINES = (Line("card", "Cartão"), Line("pix", "Pix"))


def _store(conn: sqlite3.Connection) -> LinePreferenceStore:
    return LinePreferenceStore(conn)


def test_unset_user_has_no_line(memory_db: sqlite3.Connection) -> None:
    assert _store(memory_db).get_line(USER) is None


def test_set_then_get(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.set_line(USER, "pix")
    assert store.get_line(USER) == "pix"


def test_changing_line_replaces_previous(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.set_line(USER, "card")
    store.set_line(USER, "pix")
    assert store.get_line(USER) == "pix"


def test_users_are_independent(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.set_line(USER, "card")
    store.set_line(99, "pix")
    assert store.get_line(USER) == "card"
    assert store.get_line(99) == "pix"


def test_chosen_line_returns_the_configured_line(
    memory_db: sqlite3.Connection,
) -> None:
    store = _store(memory_db)
    store.set_line(USER, "pix")
    assert chosen_line(store, LINES, USER) == Line("pix", "Pix")


def test_chosen_line_is_none_when_unset(memory_db: sqlite3.Connection) -> None:
    assert chosen_line(_store(memory_db), LINES, USER) is None


def test_chosen_line_is_none_when_stale(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.set_line(USER, "ghost")  # no longer in config
    assert chosen_line(store, LINES, USER) is None
