"""Tests for the raw-sample store.

Samples are transit times in seconds. These cover the bucket key (a sample is
only read back for its exact line/weekday/block), the half-open time window
(since inclusive, until exclusive — the anti-anchoring split), and pruning.
"""

import sqlite3
from datetime import UTC, datetime, time, timedelta

import pytest

from enfilera.samples_store import SampleStore

BLOCK = time(12, 0)
NOON = datetime(2026, 6, 30, 12, 5, tzinfo=UTC)


def _store(conn: sqlite3.Connection) -> SampleStore:
    return SampleStore(conn)


# --- add + read back -----------------------------------------------------


def test_add_then_read_value(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.add("card", 2, BLOCK, 720, NOON)
    values = store.values_in_window("card", 2, BLOCK, NOON - timedelta(hours=1))
    assert values == [720]


def test_add_rejects_non_positive_value(memory_db: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="positive seconds"):
        _store(memory_db).add("card", 2, BLOCK, 0, NOON)


# --- bucket isolation ----------------------------------------------------


def test_window_filters_by_line(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.add("card", 2, BLOCK, 600, NOON)
    store.add("pix", 2, BLOCK, 999, NOON)
    since = NOON - timedelta(hours=1)
    assert store.values_in_window("card", 2, BLOCK, since) == [600]


def test_window_filters_by_weekday_and_block(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.add("card", 2, BLOCK, 600, NOON)
    store.add("card", 3, BLOCK, 601, NOON)  # other weekday
    store.add("card", 2, time(13, 0), 602, NOON)  # other block
    since = NOON - timedelta(hours=1)
    assert store.values_in_window("card", 2, BLOCK, since) == [600]


def test_empty_bucket_returns_empty(memory_db: sqlite3.Connection) -> None:
    since = NOON - timedelta(hours=1)
    assert _store(memory_db).values_in_window("card", 2, BLOCK, since) == []


# --- time window: since inclusive, until exclusive -----------------------


def test_since_is_inclusive(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.add("card", 2, BLOCK, 600, NOON)
    assert store.values_in_window("card", 2, BLOCK, NOON) == [600]


def test_recorded_before_since_is_excluded(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.add("card", 2, BLOCK, 600, NOON)
    assert store.values_in_window("card", 2, BLOCK, NOON + timedelta(minutes=1)) == []


def test_until_is_exclusive(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    store.add("card", 2, BLOCK, 600, NOON)
    since = NOON - timedelta(hours=1)
    # until == the exact recorded time excludes the sample (half-open window).
    assert store.values_in_window("card", 2, BLOCK, since, until=NOON) == []


def test_window_splits_history_from_today(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    last_week = NOON - timedelta(days=7)
    store.add("card", 2, BLOCK, 600, last_week)  # historical
    store.add("card", 2, BLOCK, 900, NOON)  # today
    today_start = NOON.replace(hour=0, minute=0)
    history = store.values_in_window("card", 2, BLOCK, last_week, until=today_start)
    today = store.values_in_window("card", 2, BLOCK, today_start)
    assert history == [600]
    assert today == [900]


# --- pruning -------------------------------------------------------------


def test_prune_removes_old_keeps_recent(memory_db: sqlite3.Connection) -> None:
    store = _store(memory_db)
    old = NOON - timedelta(days=40)
    store.add("card", 2, BLOCK, 600, old)
    store.add("card", 2, BLOCK, 700, NOON)
    removed = store.prune_older_than(NOON - timedelta(days=30))
    assert removed == 1
    assert store.values_in_window("card", 2, BLOCK, old - timedelta(days=1)) == [700]


def test_prune_empty_removes_nothing(memory_db: sqlite3.Connection) -> None:
    assert _store(memory_db).prune_older_than(NOON) == 0
