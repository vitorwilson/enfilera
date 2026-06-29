"""Persistence for the one-submission-per-period rule.

Keeps only the *latest* period each user submitted in (one row per user), so
the table is bounded by the user count and never needs pruning. The check is
exact: a user has already submitted this period iff their stored
(date, period) equals the current one — and that current period is resolved
from server time by the caller, never the device clock (docs/PLAN.md §3).
"""

from __future__ import annotations

import sqlite3
from datetime import date


class SubmissionStore:
    """Record and query a user's last submission over an injected connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def mark(self, user_id: int, period_date: date, period_id: str) -> None:
        """Record that ``user_id`` submitted in (``period_date``, ``period_id``).

        Overwrites the user's previous period, so marking a new period
        re-arms them for it while disabling the one just used.
        """
        with self._conn:
            self._conn.execute(
                "INSERT INTO submissions (user_id, period_date, period_id) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "period_date = excluded.period_date, period_id = excluded.period_id",
                (user_id, period_date.isoformat(), period_id),
            )

    def has_submitted(self, user_id: int, period_date: date, period_id: str) -> bool:
        """Whether ``user_id``'s last submission is exactly this period."""
        row = self._conn.execute(
            "SELECT 1 FROM submissions "
            "WHERE user_id = ? AND period_date = ? AND period_id = ?",
            (user_id, period_date.isoformat(), period_id),
        ).fetchone()
        return row is not None
