"""Persistence for the halt flag — the operator's indefinite pause.

A single-row table (its ``id`` pinned to 1) holding one boolean. Halt is the
highest-precedence closed reason in openness.py: when enabled the bot accepts
no timers regardless of hours or closures, until an admin resumes it. Seeded
disabled on first migration (db.py), so a fresh fork starts open.
"""

from __future__ import annotations

import sqlite3


class HaltFlag:
    """Read and write the halt flag over an injected connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def is_enabled(self) -> bool:
        """Whether the bot is currently halted."""
        row = self._conn.execute("SELECT enabled FROM halt WHERE id = 1").fetchone()
        return bool(row["enabled"])

    def set(self, enabled: bool) -> None:
        """Halt (``True``) or resume (``False``) the bot."""
        with self._conn:
            self._conn.execute(
                "UPDATE halt SET enabled = ? WHERE id = 1", (int(enabled),)
            )
