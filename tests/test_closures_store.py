"""Tests for the closure store.

Covers the four operations the admin surface needs (declare, list upcoming,
active-on, revoke) plus range expansion and pruning. Revoke is first-class
here: a stale or wrong closure must never silently keep the bot dark
(docs/PLAN.md §4).
"""

import sqlite3
from datetime import date

import pytest

from enfilera.closures import Closure
from enfilera.closures_store import ClosureStore

DAY = date(2026, 6, 30)
NEXT = date(2026, 7, 1)


def _store(conn: sqlite3.Connection) -> ClosureStore:
    return ClosureStore(conn)


# --- declare + active_on -------------------------------------------------


def test_declare_whole_day_then_active(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.declare(Closure(DAY, period_id=None, reason="feriado"))
    assert store.active_on(DAY) == [Closure(DAY, None, "feriado")]


def test_declare_period_only(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.declare(Closure(DAY, period_id="lunch", reason="sem almoço"))
    assert store.active_on(DAY) == [Closure(DAY, "lunch", "sem almoço")]


def test_active_on_other_date_is_empty(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.declare(Closure(DAY, period_id=None))
    assert store.active_on(NEXT) == []


def test_whole_day_and_period_coexist_on_same_date(
    memory_db: sqlite3.Connection,
) -> None:
    store = _store(memory_db)
    store.declare(Closure(DAY, period_id=None, reason="all"))
    store.declare(Closure(DAY, period_id="lunch", reason="lunch only"))
    assert len(store.active_on(DAY)) == 2


# --- idempotent declare --------------------------------------------------


def test_redeclare_updates_reason_without_duplicating(
    memory_db: sqlite3.Connection,
) -> None:
    store = _store(memory_db)
    store.declare(Closure(DAY, period_id=None, reason="first"))
    store.declare(Closure(DAY, period_id=None, reason="second"))
    assert store.active_on(DAY) == [Closure(DAY, None, "second")]


# --- declare_range -------------------------------------------------------


def test_range_inserts_one_row_per_day(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    count = store.declare_range(date(2026, 6, 30), date(2026, 7, 2), reason="recess")
    assert count == 3
    assert store.active_on(date(2026, 7, 1)) == [
        Closure(date(2026, 7, 1), None, "recess")
    ]


def test_range_single_day(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    assert store.declare_range(DAY, DAY) == 1


def test_range_rejects_end_before_start(memory_db: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="precedes start"):
        _store(memory_db).declare_range(NEXT, DAY)


def test_single_day_revocable_out_of_range(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.declare_range(date(2026, 6, 30), date(2026, 7, 2), reason="recess")
    assert store.revoke(date(2026, 7, 1)) is True
    assert store.active_on(date(2026, 7, 1)) == []
    assert len(store.active_on(date(2026, 6, 30))) == 1  # neighbours untouched


# --- upcoming ------------------------------------------------------------


def test_upcoming_excludes_past_and_orders(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.declare(Closure(date(2026, 7, 5), None, "later"))
    store.declare(Closure(date(2026, 7, 2), None, "sooner"))
    store.declare(Closure(date(2026, 6, 1), None, "past"))
    upcoming = store.upcoming(DAY)
    assert [c.date for c in upcoming] == [date(2026, 7, 2), date(2026, 7, 5)]


def test_upcoming_orders_whole_day_before_period(
    memory_db: sqlite3.Connection,
) -> None:
    store = _store(memory_db)
    store.declare(Closure(DAY, period_id="lunch"))
    store.declare(Closure(DAY, period_id=None))
    # NULL period sorts first, so the whole-day record leads its date.
    assert [c.period_id for c in store.upcoming(DAY)] == [None, "lunch"]


# --- revoke --------------------------------------------------------------


def test_revoke_period_leaves_whole_day(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.declare(Closure(DAY, period_id=None, reason="all"))
    store.declare(Closure(DAY, period_id="lunch"))
    assert store.revoke(DAY, "lunch") is True
    assert store.active_on(DAY) == [Closure(DAY, None, "all")]


def test_revoke_whole_day_leaves_period(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.declare(Closure(DAY, period_id=None))
    store.declare(Closure(DAY, period_id="lunch", reason="keep"))
    assert store.revoke(DAY, None) is True
    assert store.active_on(DAY) == [Closure(DAY, "lunch", "keep")]


def test_revoke_missing_returns_false(memory_db: sqlite3.Connection) -> None:
    assert _store(memory_db).revoke(DAY) is False


# --- pruning -------------------------------------------------------------


def test_prune_before_drops_past_keeps_today(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.declare(Closure(date(2026, 6, 1), None, "past"))
    store.declare(Closure(DAY, None, "today"))
    removed = store.prune_before(DAY)
    assert removed == 1
    assert [c.date for c in store.upcoming(date(2026, 1, 1))] == [DAY]
