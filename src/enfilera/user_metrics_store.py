"""Read-only user-activity metrics over the submissions table.

The submissions table keeps one row per user holding their *most-recent*
submission (date, period, line). Because that date is the latest, a user is
"active in the last N days" exactly when their row's ``period_date`` falls in
the window — so these ``COUNT`` queries give exact distinct-active-user
figures for the operator's ``/usuarios`` read, without storing any per-sample
identity (samples stay anonymous). The connection is injected — this store
never opens the database itself.
"""

from __future__ import annotations

import sqlite3
from datetime import date


class UserMetricsStore:
    """Count distinct active users over an injected connection (read-only)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def active_on(self, day: date) -> int:
        """Distinct users whose latest submission is dated exactly ``day``."""
        row = self._conn.execute(
            "SELECT count(*) FROM submissions WHERE period_date = ?",
            (day.isoformat(),),
        ).fetchone()
        return row[0]

    def active_since(self, cutoff: date) -> int:
        """Distinct users active on or after ``cutoff`` (inclusive)."""
        row = self._conn.execute(
            "SELECT count(*) FROM submissions WHERE period_date >= ?",
            (cutoff.isoformat(),),
        ).fetchone()
        return row[0]

    def per_line_since(self, cutoff: date) -> dict[str | None, int]:
        """Active-user counts on or after ``cutoff``, grouped by latest line.

        Keys are line ids; a ``None`` key holds rows written before the line
        column existed (or a since-removed line). The counts sum to
        :meth:`active_since` for the same ``cutoff`` — every active user falls
        in exactly one line bucket.
        """
        rows = self._conn.execute(
            "SELECT line_id, count(*) AS n FROM submissions "
            "WHERE period_date >= ? GROUP BY line_id",
            (cutoff.isoformat(),),
        ).fetchall()
        return {row["line_id"]: row["n"] for row in rows}
