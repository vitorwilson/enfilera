"""Tests for the one-submission-per-period store.

The rule: a user may submit once per (date, period). Re-marking a *new*
period must release the old one (single row per user), so the same person can
submit again at dinner after lunch, but not twice at lunch.
"""

import sqlite3
from datetime import date

from enfilera.submissions_store import SubmissionStore

USER = 42
TODAY = date(2026, 6, 30)
TOMORROW = date(2026, 7, 1)
CARD = "card"


def _store(conn: sqlite3.Connection) -> SubmissionStore:
    return SubmissionStore(conn)


def _stored_line(conn: sqlite3.Connection, user_id: int) -> str | None:
    row = conn.execute(
        "SELECT line_id FROM submissions WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row["line_id"]


def test_unmarked_user_has_not_submitted(memory_db: sqlite3.Connection) -> None:
    assert _store(memory_db).has_submitted(USER, TODAY, "lunch") is False


def test_mark_then_has_submitted(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.mark(USER, TODAY, "lunch", CARD)
    assert store.has_submitted(USER, TODAY, "lunch") is True


def test_other_period_same_day_not_submitted(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.mark(USER, TODAY, "lunch", CARD)
    assert store.has_submitted(USER, TODAY, "dinner") is False


def test_other_day_not_submitted(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.mark(USER, TODAY, "lunch", CARD)
    assert store.has_submitted(USER, TOMORROW, "lunch") is False


def test_other_user_not_submitted(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.mark(USER, TODAY, "lunch", CARD)
    assert store.has_submitted(99, TODAY, "lunch") is False


def test_marking_new_period_releases_the_old(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.mark(USER, TODAY, "lunch", CARD)
    store.mark(USER, TODAY, "dinner", CARD)
    assert store.has_submitted(USER, TODAY, "lunch") is False
    assert store.has_submitted(USER, TODAY, "dinner") is True


def test_marking_same_period_twice_stays_submitted(
    memory_db: sqlite3.Connection,
) -> None:
    store = _store(memory_db)
    store.mark(USER, TODAY, "lunch", CARD)
    store.mark(USER, TODAY, "lunch", CARD)
    assert store.has_submitted(USER, TODAY, "lunch") is True


def test_mark_persists_the_line(memory_db: sqlite3.Connection) -> None:
    _store(memory_db).mark(USER, TODAY, "lunch", CARD)
    assert _stored_line(memory_db, USER) == CARD


def test_remarking_overwrites_the_line(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.mark(USER, TODAY, "lunch", CARD)
    store.mark(USER, TODAY, "dinner", "pix")
    assert _stored_line(memory_db, USER) == "pix"
