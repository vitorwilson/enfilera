"""Tests for the read-only user-activity metrics store.

Since the submissions table holds one row per user with their *latest*
submission, distinct-active counts fall straight out of a date filter, and a
per-line GROUP BY partitions those users with no double-counting — a user's
row carries only their most-recent line. Rows are written through the real
SubmissionStore over the in-memory DB (the wrapper *is* the SQL).
"""

from __future__ import annotations

import sqlite3
from datetime import date

from enfilera.submissions_store import SubmissionStore
from enfilera.user_metrics_store import UserMetricsStore

TODAY = date(2026, 6, 30)
CUTOFF = date(2026, 6, 1)
OLD = date(2026, 5, 1)  # before the cutoff


def _mark(conn: sqlite3.Connection, user_id: int, when: date, line: str) -> None:
    SubmissionStore(conn).mark(user_id, when, "lunch", line)


def test_active_on_counts_only_that_day(memory_db: sqlite3.Connection) -> None:
    _mark(memory_db, 1, TODAY, "card")
    _mark(memory_db, 2, TODAY, "pix")
    _mark(memory_db, 3, CUTOFF, "card")
    assert UserMetricsStore(memory_db).active_on(TODAY) == 2


def test_active_on_is_zero_with_no_submissions(memory_db: sqlite3.Connection) -> None:
    assert UserMetricsStore(memory_db).active_on(TODAY) == 0


def test_active_since_is_inclusive_of_the_cutoff(memory_db: sqlite3.Connection) -> None:
    _mark(memory_db, 1, TODAY, "card")
    _mark(memory_db, 2, CUTOFF, "pix")
    _mark(memory_db, 3, OLD, "card")  # excluded: before the window
    assert UserMetricsStore(memory_db).active_since(CUTOFF) == 2


def test_latest_submission_defines_activity(memory_db: sqlite3.Connection) -> None:
    # Marking again overwrites the row, so an old-then-recent user still counts.
    _mark(memory_db, 1, OLD, "card")
    _mark(memory_db, 1, TODAY, "card")
    assert UserMetricsStore(memory_db).active_since(CUTOFF) == 1


def test_per_line_partitions_active_users(memory_db: sqlite3.Connection) -> None:
    _mark(memory_db, 1, TODAY, "card")
    _mark(memory_db, 2, TODAY, "card")
    _mark(memory_db, 3, TODAY, "pix")
    _mark(memory_db, 4, OLD, "pix")  # excluded by the cutoff
    counts = UserMetricsStore(memory_db).per_line_since(CUTOFF)
    assert counts == {"card": 2, "pix": 1}


def test_per_line_sums_to_active_since(memory_db: sqlite3.Connection) -> None:
    _mark(memory_db, 1, TODAY, "card")
    _mark(memory_db, 2, CUTOFF, "pix")
    _mark(memory_db, 3, TODAY, "pix")
    store = UserMetricsStore(memory_db)
    assert sum(store.per_line_since(CUTOFF).values()) == store.active_since(CUTOFF)


def test_switcher_counts_once_under_latest_line(memory_db: sqlite3.Connection) -> None:
    _mark(memory_db, 1, CUTOFF, "card")
    _mark(memory_db, 1, TODAY, "pix")  # switched lines; only the latest survives
    assert UserMetricsStore(memory_db).per_line_since(CUTOFF) == {"pix": 1}


def test_per_line_keeps_null_line_bucket(memory_db: sqlite3.Connection) -> None:
    # A pre-migration row (no line) must still be counted, under the None key.
    memory_db.execute(
        "INSERT INTO submissions (user_id, period_date, period_id) VALUES (?, ?, ?)",
        (9, TODAY.isoformat(), "lunch"),
    )
    memory_db.commit()
    assert UserMetricsStore(memory_db).per_line_since(CUTOFF) == {None: 1}
