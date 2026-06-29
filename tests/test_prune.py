"""Tests for the pruning entrypoint (`python -m enfilera.prune`).

Drives the real wiring — load config, open the DB, prune — against a temp
SQLite file and the committed example config, so the scheduled job is proven
to actually delete past-retention rows (not just the pure `run_pruning` core,
which `test_pruning.py` covers). 2026-06-29 is the run instant; the example
config keeps 30 days.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

from enfilera import prune
from enfilera.closures import Closure
from enfilera.closures_store import ClosureStore
from enfilera.db import connect
from enfilera.samples_store import SampleStore

EXAMPLE = Path(__file__).resolve().parent.parent / "config" / "config.example.toml"
NOW = datetime(2026, 6, 29, 4, 0, tzinfo=UTC)


def _seed(db_path: str) -> None:
    conn = connect(db_path)
    try:
        SampleStore(conn).add("card", 1, time(12, 0), 600, NOW - timedelta(days=40))
        SampleStore(conn).add("card", 1, time(12, 0), 600, NOW - timedelta(days=1))
        ClosureStore(conn).declare(Closure((NOW - timedelta(days=5)).date(), None))
    finally:
        conn.close()


def test_run_prunes_past_retention_rows(tmp_path: Path) -> None:
    db_path = str(tmp_path / "enfilera.db")
    _seed(db_path)

    result = prune.run(str(EXAMPLE), db_path, NOW)

    assert result.samples_removed == 1  # the 40-day-old sample; the 1-day stays
    assert result.closures_removed == 1
    survivors = connect(db_path).execute("SELECT COUNT(*) AS n FROM samples").fetchone()
    assert survivors["n"] == 1


def test_main_resolves_paths_from_env(tmp_path: Path) -> None:
    db_path = str(tmp_path / "enfilera.db")
    _seed(db_path)
    env = {"ENFILERA_CONFIG": str(EXAMPLE), "ENFILERA_DB": db_path}

    prune.main(env, lambda: NOW)

    remaining: sqlite3.Connection = connect(db_path)
    assert remaining.execute("SELECT COUNT(*) AS n FROM samples").fetchone()["n"] == 1
