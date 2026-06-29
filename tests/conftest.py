"""Shared pytest fixtures for the persistence layer.

Stores are tested against a real in-memory SQLite database (the sanctioned
in-memory DB from docs/PLAN.md), not a hand-rolled mock: the wrapper *is* the
SQL, so faking it would test nothing. Each test gets a fresh, migrated
connection — fast and fully isolated (F.I.R.S.T).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest

from enfilera.db import connect


@pytest.fixture
def memory_db() -> Iterator[sqlite3.Connection]:
    conn = connect(":memory:")
    try:
        yield conn
    finally:
        conn.close()
