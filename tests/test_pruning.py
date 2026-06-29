"""Tests for the pruning job.

Exercised over a real in-memory database with both stores, so the cutoff
arithmetic (retention window for samples, local date for closures) is checked
end to end. The window boundary matters: a sample exactly at the retention
edge is kept, and today's closure survives.
"""

import sqlite3
from datetime import UTC, datetime, time, timedelta

import pytest

from enfilera.closures import Closure
from enfilera.closures_store import ClosureStore
from enfilera.pruning import run_pruning
from enfilera.samples_store import SampleStore

NOW = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
BLOCK = time(12, 0)
RETENTION = 30


def _stores(conn: sqlite3.Connection) -> tuple[SampleStore, ClosureStore]:
    return SampleStore(conn), ClosureStore(conn)


def test_prunes_old_samples_and_past_closures(memory_db: sqlite3.Connection) -> None:
    samples, closures = _stores(memory_db)
    samples.add("card", 2, BLOCK, 600, NOW - timedelta(days=40))  # too old
    samples.add("card", 2, BLOCK, 700, NOW)  # fresh
    closures.declare(Closure(date=(NOW - timedelta(days=2)).date(), period_id=None))
    closures.declare(Closure(date=NOW.date(), period_id=None))  # today, kept

    result = run_pruning(samples, closures, NOW, RETENTION)

    assert result.samples_removed == 1
    assert result.closures_removed == 1
    assert samples.values_in_window("card", 2, BLOCK, NOW - timedelta(days=60)) == [700]
    assert [c.date for c in closures.upcoming(NOW.date())] == [NOW.date()]


def test_keeps_sample_exactly_at_retention_edge(
    memory_db: sqlite3.Connection,
) -> None:
    samples, closures = _stores(memory_db)
    # cutoff is NOW - 30d; a sample AT the cutoff is not "older than" it.
    samples.add("card", 2, BLOCK, 600, NOW - timedelta(days=RETENTION))
    result = run_pruning(samples, closures, NOW, RETENTION)
    assert result.samples_removed == 0


def test_rejects_non_positive_retention(memory_db: sqlite3.Connection) -> None:
    samples, closures = _stores(memory_db)
    with pytest.raises(ValueError, match="retention_days must be positive"):
        run_pruning(samples, closures, NOW, 0)
