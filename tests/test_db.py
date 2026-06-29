"""Tests for the connection factory and schema migrations.

A fresh database must come up empty-clean with every table present and the
schema version stamped, and re-running migrations must be a no-op.
"""

import sqlite3
from datetime import UTC, datetime

import pytest

from enfilera.db import SCHEMA_VERSION, migrate, to_epoch


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row["name"] for row in rows}


# --- schema creation -----------------------------------------------------


def test_connect_creates_every_table(memory_db: sqlite3.Connection) -> None:
    assert {"samples", "submissions", "closures", "halt"} <= _tables(memory_db)


def test_connect_stamps_schema_version(memory_db: sqlite3.Connection) -> None:
    version = memory_db.execute("PRAGMA user_version").fetchone()[0]
    assert version == SCHEMA_VERSION


def test_fresh_database_is_empty(memory_db: sqlite3.Connection) -> None:
    count = memory_db.execute("SELECT count(*) FROM samples").fetchone()[0]
    assert count == 0


def test_halt_seeded_disabled(memory_db: sqlite3.Connection) -> None:
    enabled = memory_db.execute("SELECT enabled FROM halt WHERE id = 1").fetchone()[0]
    assert enabled == 0


# --- migrations idempotent ----------------------------------------------


def test_migrate_is_idempotent(memory_db: sqlite3.Connection) -> None:
    # connect() already migrated once; a second run must not error or change
    # the stamped version.
    migrate(memory_db)
    version = memory_db.execute("PRAGMA user_version").fetchone()[0]
    assert version == SCHEMA_VERSION


# --- to_epoch ------------------------------------------------------------


def test_to_epoch_converts_utc() -> None:
    assert to_epoch(datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)) == 1


def test_to_epoch_rejects_naive() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        to_epoch(datetime(2026, 6, 28, 12, 0))
