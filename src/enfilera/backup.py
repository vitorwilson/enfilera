"""The backup entrypoint: ``python -m enfilera.backup``.

Writes a consistent snapshot of the live database and rotates old ones, once
per run. The ``backup`` sidecar in ``compose.yaml`` runs it daily, so backups
ship with the deploy (no host cron); run it on demand with
``docker compose run --rm backup python -m enfilera.backup``. It uses SQLite's
online backup API, so the bot keeps serving during a snapshot — no downtime and
no torn ``cp`` of a file mid-write. It loads the same static config and database
as the bot, keeps the most recent ``[backup].keep`` snapshots, logs the result
as one JSON line, and exits.
"""

from __future__ import annotations

import glob
import logging
import os
import sqlite3
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from enfilera.backups import GLOB, BackupResult, run_backup
from enfilera.config_loader import load_config
from enfilera.json_logging import configure_logging

_logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = "config/config.toml"
_DEFAULT_DB = "enfilera.db"
_DEFAULT_BACKUP_DIR = "backups"


def _write_snapshot(source_db: str, dest: str) -> None:
    """Copy the live DB to ``dest`` with SQLite's online backup — consistent
    even while the bot writes. Written to a temp file and atomically renamed, so
    a crash mid-snapshot never leaves a half-written file under the final name.
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = f"{dest}.tmp"
    # Read-only source: the backup must never migrate or otherwise mutate the
    # live database (enfilera.db.connect would run migrations on open).
    source = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    try:
        target = sqlite3.connect(tmp)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    os.replace(tmp, dest)


def _existing_snapshots(backup_dir: str) -> list[str]:
    return glob.glob(os.path.join(backup_dir, GLOB))


def run(
    config_path: str | Path, db_path: str, backup_dir: str, now: datetime
) -> BackupResult:
    """Snapshot the database and rotate, keeping ``[backup].keep`` from config."""
    config = load_config(config_path)
    result = run_backup(
        snapshot=lambda dest: _write_snapshot(db_path, dest),
        list_existing=lambda: _existing_snapshots(backup_dir),
        remove=os.remove,
        backup_dir=backup_dir,
        keep=config.backup_keep,
        now=now,
    )
    # NB: avoid keys that shadow reserved LogRecord attributes (e.g. `created`
    # is the record's own timestamp), which makeRecord rejects with a KeyError.
    _logger.info(
        "backup complete",
        extra={"snapshot": result.created, "rotated": len(result.removed)},
    )
    return result


def main(
    env: Mapping[str, str] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> None:
    """Resolve paths from the environment and run one backup pass."""
    resolved = os.environ if env is None else env
    configure_logging()
    run(
        resolved.get("ENFILERA_CONFIG", _DEFAULT_CONFIG),
        resolved.get("ENFILERA_DB", _DEFAULT_DB),
        resolved.get("ENFILERA_BACKUP_DIR", _DEFAULT_BACKUP_DIR),
        now(),
    )


if __name__ == "__main__":
    main()
