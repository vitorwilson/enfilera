"""Persistence for each user's chosen line.

A user picks their line once (card / pix / …) and it sticks until they change
it; every "how's the line?" and submission uses it (docs/PLAN.md §4). One row
per user keeps the table bounded and never in need of pruning. The connection
is injected — this store never opens the database itself.
"""

from __future__ import annotations

import sqlite3


class LinePreferenceStore:
    """Read and write a user's selected line over an injected connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def set_line(self, user_id: int, line_id: str) -> None:
        """Set ``user_id``'s chosen line, replacing any previous choice."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO user_lines (user_id, line_id) VALUES (?, ?) "
                "ON CONFLICT (user_id) DO UPDATE SET line_id = excluded.line_id",
                (user_id, line_id),
            )

    def get_line(self, user_id: int) -> str | None:
        """``user_id``'s chosen line id, or ``None`` if they haven't picked one."""
        row = self._conn.execute(
            "SELECT line_id FROM user_lines WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["line_id"] if row is not None else None
