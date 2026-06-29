"""Persistence for dynamic closure records.

One row per closed day: a declared *range* is expanded to one row per day so
the active-lookup stays trivial and a single day can be revoked out of the
range. Whole-day closures store ``period_id`` as NULL; the unique index over
``(date, ifnull(period_id, ''))`` (see db.py) makes re-declaring idempotent
and revoke exact. Returns the domain :class:`~enfilera.closures.Closure` so
the openness check can consume rows directly.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from enfilera.closures import Closure

_UPSERT = (
    "INSERT INTO closures (closure_date, period_id, reason) VALUES (?, ?, ?) "
    "ON CONFLICT (closure_date, ifnull(period_id, '')) "
    "DO UPDATE SET reason = excluded.reason"
)
_SELECT = "SELECT closure_date, period_id, reason FROM closures"


class ClosureStore:
    """Declare, list, revoke, and prune closures over an injected connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def declare(self, closure: Closure) -> None:
        """Insert one closure, replacing the reason if it already exists."""
        with self._conn:
            self._conn.execute(
                _UPSERT, (closure.date.isoformat(), closure.period_id, closure.reason)
            )

    def declare_range(
        self,
        start: date,
        end: date,
        period_id: str | None = None,
        reason: str | None = None,
    ) -> int:
        """Declare a closure for every day in ``[start, end]``; return the count.

        Stored as one record per day, so a single day can later be revoked.
        """
        if end < start:
            raise ValueError(f"closure range end {end} precedes start {start}")
        days = _days_inclusive(start, end)
        with self._conn:
            for day in days:
                self._conn.execute(_UPSERT, (day.isoformat(), period_id, reason))
        return len(days)

    def active_on(self, on: date) -> list[Closure]:
        """Every closure record for ``on`` (whole-day and period-specific)."""
        rows = self._conn.execute(
            f"{_SELECT} WHERE closure_date = ?", (on.isoformat(),)
        ).fetchall()
        return [_to_closure(row) for row in rows]

    def upcoming(self, on_or_after: date) -> list[Closure]:
        """Closures on or after ``on_or_after``, ordered by date then period."""
        rows = self._conn.execute(
            f"{_SELECT} WHERE closure_date >= ? ORDER BY closure_date, period_id",
            (on_or_after.isoformat(),),
        ).fetchall()
        return [_to_closure(row) for row in rows]

    def revoke(self, on: date, period_id: str | None = None) -> bool:
        """Remove the closure for (``on``, ``period_id``); True if one existed.

        ``period_id=None`` revokes the whole-day record specifically — it does
        not touch that day's period-specific closures.
        """
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM closures "
                "WHERE closure_date = ? AND ifnull(period_id, '') = ifnull(?, '')",
                (on.isoformat(), period_id),
            )
        return cursor.rowcount > 0

    def prune_before(self, cutoff: date) -> int:
        """Delete closures dated before ``cutoff``; return the count removed."""
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM closures WHERE closure_date < ?", (cutoff.isoformat(),)
            )
        return cursor.rowcount


def _to_closure(row: sqlite3.Row) -> Closure:
    return Closure(
        date=date.fromisoformat(row["closure_date"]),
        period_id=row["period_id"],
        reason=row["reason"],
    )


def _days_inclusive(start: date, end: date) -> list[date]:
    span = (end - start).days
    return [start + timedelta(days=offset) for offset in range(span + 1)]
