"""Persistence for raw transit-time samples.

Each sample is one anonymous (line, weekday, block) transit time in whole
seconds, stamped with the server epoch it was recorded at. The estimator
reads windows of these back to build its baseline and today's live block; the
pruning job drops samples past the retention window so the file stays bounded.
The connection is injected — this store never opens the database itself.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, time

from enfilera.db import to_epoch


class SampleStore:
    """Read, write, and prune raw samples over an injected connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(
        self,
        line_id: str,
        weekday: int,
        block_start: time,
        value: int,
        recorded_at: datetime,
    ) -> None:
        """Persist one already-validated sample (``value`` in whole seconds)."""
        if value <= 0:
            raise ValueError(f"sample value must be positive seconds, got {value}")
        with self._conn:
            self._conn.execute(
                "INSERT INTO samples "
                "(line_id, weekday, block_start, value, recorded_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (line_id, weekday, _hhmm(block_start), value, to_epoch(recorded_at)),
            )

    def values_in_window(
        self,
        line_id: str,
        weekday: int,
        block_start: time,
        since: datetime,
        until: datetime | None = None,
    ) -> list[int]:
        """Sample values for one bucket recorded in ``[since, until)``.

        ``since`` is inclusive, ``until`` exclusive (open-ended when omitted).
        The estimator uses this twice: ``until = start of today`` for the
        historical baseline, and ``since = start of today`` for today's live
        block, so today's data never anchors its own band (docs/PLAN.md §2.4).
        """
        sql = (
            "SELECT value FROM samples "
            "WHERE line_id = ? AND weekday = ? AND block_start = ? "
            "AND recorded_at >= ?"
        )
        params: list[object] = [line_id, weekday, _hhmm(block_start), to_epoch(since)]
        if until is not None:
            sql += " AND recorded_at < ?"
            params.append(to_epoch(until))
        rows = self._conn.execute(sql, params).fetchall()
        return [row["value"] for row in rows]

    def prune_older_than(self, cutoff: datetime) -> int:
        """Delete samples recorded before ``cutoff``; return the count removed."""
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM samples WHERE recorded_at < ?", (to_epoch(cutoff),)
            )
        return cursor.rowcount


def _hhmm(moment: time) -> str:
    return moment.strftime("%H:%M")
