"""Tests for the backup entrypoint (`python -m enfilera.backup`).

Drives the real wiring — load config, snapshot the live DB with SQLite's online
backup, rotate — against a temp SQLite file and the committed example config, so
the scheduled job is proven to produce a valid, consistent copy (not just the
pure `run_backup` core, which `test_backups.py` covers).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, time
from pathlib import Path

import pytest

from enfilera import backup
from enfilera.backup import _existing_snapshots, _write_snapshot
from enfilera.backups import run_backup
from enfilera.db import connect
from enfilera.samples_store import SampleStore

EXAMPLE = Path(__file__).resolve().parent.parent / "config" / "config.example.toml"
NOW = datetime(2026, 7, 4, 21, 5, 0, tzinfo=UTC)


def _seed(db_path: str) -> None:
    conn = connect(db_path)
    try:
        SampleStore(conn).add("card", 1, time(12, 0), 600, NOW)
    finally:
        conn.close()


def _sample_count(db_path: str) -> int:
    conn = connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) AS n FROM samples").fetchone()["n"]
    finally:
        conn.close()


def test_run_writes_a_valid_snapshot(tmp_path: Path) -> None:
    db_path = str(tmp_path / "enfilera.db")
    backup_dir = str(tmp_path / "backups")
    _seed(db_path)

    result = backup.run(str(EXAMPLE), db_path, backup_dir, NOW)

    assert Path(result.created).name == "enfilera-20260704-210500.db"
    assert Path(result.created).exists()
    assert result.removed == ()
    assert _sample_count(result.created) == 1  # the snapshot is a real, open-able DB


def test_write_snapshot_is_a_consistent_copy(tmp_path: Path) -> None:
    db_path = str(tmp_path / "enfilera.db")
    dest = str(tmp_path / "backups" / "snap.db")
    _seed(db_path)

    _write_snapshot(db_path, dest)

    assert Path(dest).exists()
    assert not Path(f"{dest}.tmp").exists()  # temp file promoted, not left behind
    assert _sample_count(dest) == 1


def test_write_snapshot_leaves_source_unmigrated_readonly(tmp_path: Path) -> None:
    # A snapshot must never write the live DB. Point at a path with no database;
    # the read-only open fails rather than creating/migrating an empty file.
    missing = str(tmp_path / "nope.db")
    with pytest.raises(sqlite3.OperationalError):
        _write_snapshot(missing, str(tmp_path / "out.db"))
    assert not Path(missing).exists()


def test_rotation_over_real_files(tmp_path: Path) -> None:
    db_path = str(tmp_path / "enfilera.db")
    backup_dir = str(tmp_path / "backups")
    _seed(db_path)
    args = dict(
        snapshot=lambda dest: _write_snapshot(db_path, dest),
        list_existing=lambda: _existing_snapshots(backup_dir),
        remove=os.remove,
        backup_dir=backup_dir,
        keep=1,
    )
    first = run_backup(now=NOW, **args)
    second = run_backup(now=datetime(2026, 7, 5, 21, 5, tzinfo=UTC), **args)

    assert not Path(first.created).exists()  # rotated out
    assert Path(second.created).exists()
    assert _existing_snapshots(backup_dir) == [second.created]


def test_main_resolves_paths_from_env(tmp_path: Path) -> None:
    db_path = str(tmp_path / "enfilera.db")
    backup_dir = str(tmp_path / "backups")
    _seed(db_path)
    env = {
        "ENFILERA_CONFIG": str(EXAMPLE),
        "ENFILERA_DB": db_path,
        "ENFILERA_BACKUP_DIR": backup_dir,
    }

    backup.main(env, lambda: NOW)

    snapshots = _existing_snapshots(backup_dir)
    assert len(snapshots) == 1
    assert _sample_count(snapshots[0]) == 1
