"""Tests for the halt flag.

A fresh fork must start open (resumed); halt and resume must round-trip.
"""

import sqlite3

from enfilera.halt_flag import HaltFlag


def test_fresh_fork_starts_resumed(memory_db: sqlite3.Connection) -> None:
    assert HaltFlag(memory_db).is_enabled() is False


def test_halt_then_resume(memory_db: sqlite3.Connection) -> None:
    flag = HaltFlag(memory_db)
    flag.set(True)
    assert flag.is_enabled() is True
    flag.set(False)
    assert flag.is_enabled() is False


def test_halt_persists_across_store_instances(memory_db: sqlite3.Connection) -> None:
    # State lives in the database, not the wrapper: a second HaltFlag over the
    # same connection sees the halt set by the first.
    HaltFlag(memory_db).set(True)
    assert HaltFlag(memory_db).is_enabled() is True
