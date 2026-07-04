"""Snapshot-and-rotate orchestration for the backup job.

Pure orchestration over injected side effects (make a snapshot, list existing
snapshots, delete one), so the rotation policy is unit-testable without touching
sqlite or the filesystem. Snapshots are named by UTC timestamp so a plain
lexical sort is chronological; the newest ``keep`` survive and older ones are
removed, keeping ``backups/`` bounded the way pruning keeps the DB bounded.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

_PREFIX = "enfilera-"
_SUFFIX = ".db"
_STAMP = "%Y%m%d-%H%M%S"
# Shell glob (not a regex) matching only promoted snapshots, never the
# ``.db.tmp`` a half-written one carries — see enfilera.backup._write_snapshot.
GLOB = f"{_PREFIX}*{_SUFFIX}"


@dataclass(frozen=True)
class BackupResult:
    """What one backup pass did, for the operator log."""

    created: str
    removed: tuple[str, ...]


def snapshot_name(now: datetime) -> str:
    """Timestamped snapshot filename; lexical order == chronological order.

    >>> from datetime import UTC, datetime
    >>> snapshot_name(datetime(2026, 7, 4, 21, 5, 0, tzinfo=UTC))
    'enfilera-20260704-210500.db'
    """
    return f"{_PREFIX}{now.strftime(_STAMP)}{_SUFFIX}"


def run_backup(
    snapshot: Callable[[str], None],
    list_existing: Callable[[], Sequence[str]],
    remove: Callable[[str], None],
    backup_dir: str,
    keep: int,
    now: datetime,
) -> BackupResult:
    """Write one snapshot into ``backup_dir``, then keep only the newest ``keep``.

    ``list_existing`` is read *after* the snapshot so the fresh file is counted;
    it is the newest, so it never rotates itself out.
    """
    if keep <= 0:
        raise ValueError(f"keep must be a positive integer, got {keep!r}")
    created = os.path.join(backup_dir, snapshot_name(now))
    snapshot(created)
    removed = _surplus(list_existing(), keep)
    for path in removed:
        remove(path)
    return BackupResult(created=created, removed=tuple(removed))


def _surplus(paths: Sequence[str], keep: int) -> list[str]:
    """The oldest paths beyond the newest ``keep``, by filename order."""
    ordered = sorted(paths)
    return ordered[:-keep] if keep < len(ordered) else []
