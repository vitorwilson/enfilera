"""Tests for the pure snapshot-and-rotate orchestration.

The side effects (snapshot, list, remove) are injected as a named fake dir, so
the rotation policy is exercised without sqlite or the filesystem.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from enfilera.backups import run_backup, snapshot_name

NOW = datetime(2026, 7, 4, 21, 5, 0, tzinfo=UTC)


class FakeBackupDir:
    """A backup directory whose contents live in memory.

    ``snapshot`` adds a file, ``existing`` lists them, ``remove`` deletes one —
    the three callables ``run_backup`` needs, recording what it did.
    """

    def __init__(self, existing: list[str]) -> None:
        self.files = list(existing)
        self.snapshotted: list[str] = []
        self.removed: list[str] = []

    def snapshot(self, path: str) -> None:
        self.snapshotted.append(path)
        self.files.append(path)

    def existing(self) -> list[str]:
        return list(self.files)

    def remove(self, path: str) -> None:
        self.files.remove(path)
        self.removed.append(path)


def _run(fake: FakeBackupDir, keep: int, now: datetime = NOW):
    return run_backup(fake.snapshot, fake.existing, fake.remove, "bk", keep, now)


def test_snapshot_name_is_timestamped_and_sorts_chronologically() -> None:
    earlier = snapshot_name(datetime(2026, 7, 4, 9, 0, 0, tzinfo=UTC))
    later = snapshot_name(NOW)
    assert later == "enfilera-20260704-210500.db"
    assert earlier < later  # lexical order == chronological order


def test_creates_snapshot_in_backup_dir() -> None:
    fake = FakeBackupDir([])
    result = _run(fake, keep=7)
    assert fake.snapshotted == ["bk/enfilera-20260704-210500.db"]
    assert result.created == "bk/enfilera-20260704-210500.db"
    assert result.removed == ()


def test_rotates_out_oldest_beyond_keep() -> None:
    older = ["bk/enfilera-20260701-210500.db", "bk/enfilera-20260702-210500.db"]
    fake = FakeBackupDir(older)
    result = _run(fake, keep=2)  # 2 old + 1 new = 3; keep 2 → drop the oldest
    assert fake.removed == ["bk/enfilera-20260701-210500.db"]
    assert result.removed == ("bk/enfilera-20260701-210500.db",)


def test_keeps_all_when_under_limit() -> None:
    fake = FakeBackupDir(["bk/enfilera-20260701-210500.db"])
    result = _run(fake, keep=7)
    assert fake.removed == []
    assert result.removed == ()


def test_never_rotates_the_fresh_snapshot() -> None:
    older = [f"bk/enfilera-2026070{d}-210500.db" for d in (1, 2, 3)]
    fake = FakeBackupDir(older)
    result = _run(fake, keep=1)  # keep only the newest — the one just written
    assert result.created not in fake.removed
    assert fake.files == [result.created]


def test_rejects_non_positive_keep() -> None:
    fake = FakeBackupDir([])
    with pytest.raises(ValueError, match="keep must be a positive integer"):
        _run(fake, keep=0)
    assert fake.snapshotted == []  # guarded before any snapshot is written
