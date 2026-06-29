"""SQLite connection factory and schema migrations.

The persistence layer is a thin wrapper over a single SQLite file — one Pi,
trivial to back up and to fork. Connections are created here and *injected*
into the per-entity stores; nothing else opens the database. Schema state is
tracked with SQLite's built-in ``PRAGMA user_version`` so a fresh fork comes
up empty-clean and future schema changes apply in order.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

# Ordered DDL migrations. Entry *i* upgrades the schema from version *i* to
# *i+1*; ``migrate`` runs every entry above the database's current
# ``user_version``. Append new migrations here — never edit a shipped one.
_MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE samples (
        id INTEGER PRIMARY KEY,
        line_id TEXT NOT NULL,
        weekday INTEGER NOT NULL,        -- ISO weekday 1..7
        block_start TEXT NOT NULL,       -- bucket start time-of-day "HH:MM"
        value INTEGER NOT NULL,          -- transit time, whole seconds
        recorded_at INTEGER NOT NULL     -- server epoch seconds (UTC)
    );
    CREATE INDEX idx_samples_bucket
        ON samples (line_id, weekday, block_start, recorded_at);
    CREATE INDEX idx_samples_recorded_at ON samples (recorded_at);

    CREATE TABLE submissions (
        user_id INTEGER PRIMARY KEY,     -- one row per user: their last period
        period_date TEXT NOT NULL,       -- "YYYY-MM-DD"
        period_id TEXT NOT NULL
    );

    CREATE TABLE closures (
        closure_date TEXT NOT NULL,      -- "YYYY-MM-DD"
        period_id TEXT,                  -- NULL = whole day
        reason TEXT
    );
    -- Uniqueness must treat whole-day (NULL) as a single slot, so declaring
    -- the same closure twice is idempotent and revoke is exact.
    CREATE UNIQUE INDEX idx_closures_unique
        ON closures (closure_date, ifnull(period_id, ''));

    CREATE TABLE halt (
        id INTEGER PRIMARY KEY CHECK (id = 1),   -- singleton row
        enabled INTEGER NOT NULL
    );
    INSERT INTO halt (id, enabled) VALUES (1, 0);
    """,
    """
    CREATE TABLE user_lines (
        user_id INTEGER PRIMARY KEY,     -- one row per user: their chosen line
        line_id TEXT NOT NULL
    );
    """,
)

SCHEMA_VERSION = len(_MIGRATIONS)


def connect(path: str) -> sqlite3.Connection:
    """Open (or create) the database at ``path`` and bring its schema current.

    Pass ``":memory:"`` for tests. The returned connection yields
    ``sqlite3.Row`` rows and is migrated to :data:`SCHEMA_VERSION`.
    """
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Apply every pending migration in order (idempotent; safe to re-run)."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for target, script in enumerate(_MIGRATIONS[version:], start=version + 1):
        conn.executescript(script)
        conn.execute(f"PRAGMA user_version = {target}")
    conn.commit()


def to_epoch(moment: datetime) -> int:
    """Whole-second UTC epoch of a timezone-aware datetime.

    Naive datetimes are rejected: server time must carry its zone so a user's
    device clock can never set a sample's timestamp (docs/PLAN.md §3).

    >>> from datetime import UTC, datetime
    >>> to_epoch(datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC))
    1
    """
    if moment.tzinfo is None:
        raise ValueError(f"moment must be timezone-aware, got naive {moment!r}")
    return int(moment.timestamp())
