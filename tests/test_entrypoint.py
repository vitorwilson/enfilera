"""Tests for the container entrypoint privilege-drop shim.

The side effects (chown, privilege drop, exec) are injected into ``main`` so
the branch logic is exercised without actually being root; the filesystem
helpers are tested against a real tmp dir by chowning to the current user
(a no-op the kernel permits without privileges).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from enfilera import entrypoint


def test_data_dir_derives_from_db_path() -> None:
    assert (
        entrypoint.data_dir({"ENFILERA_DB": "/srv/app/state/db.sqlite"})
        == "/srv/app/state"
    )


def test_data_dir_falls_back_to_default() -> None:
    assert entrypoint.data_dir({}) == "/app/data"


def test_writable_dirs_covers_data_and_backups() -> None:
    assert entrypoint.writable_dirs(
        {"ENFILERA_DB": "/app/data/enfilera.db", "ENFILERA_BACKUP_DIR": "/app/backups"}
    ) == ["/app/data", "/app/backups"]


def test_writable_dirs_falls_back_to_defaults() -> None:
    assert entrypoint.writable_dirs({}) == ["/app/data", "/app/backups"]


def test_main_chowns_then_execs_when_root() -> None:
    events: list[tuple[str, object]] = []
    entrypoint.main(
        ["entrypoint.py", "python", "-m", "enfilera"],
        {"ENFILERA_DB": "/app/data/enfilera.db", "ENFILERA_BACKUP_DIR": "/app/backups"},
        is_root=lambda: True,
        take_ownership=lambda directories: events.append(("chown", list(directories))),
        exec_command=lambda command: events.append(("exec", list(command))),
    )
    assert events == [
        ("chown", ["/app/data", "/app/backups"]),
        ("exec", ["python", "-m", "enfilera"]),
    ]


def test_main_skips_chown_when_not_root() -> None:
    events: list[tuple[str, object]] = []
    entrypoint.main(
        ["entrypoint.py", "sh", "-c", "loop"],
        {},
        is_root=lambda: False,
        take_ownership=lambda directories: events.append(("chown", list(directories))),
        exec_command=lambda command: events.append(("exec", list(command))),
    )
    assert events == [("exec", ["sh", "-c", "loop"])]


def test_main_rejects_missing_command() -> None:
    with pytest.raises(SystemExit) as excinfo:
        entrypoint.main(
            ["entrypoint.py"],
            {},
            is_root=lambda: True,
            take_ownership=lambda directories: None,
            exec_command=lambda command: None,
        )
    assert "no command" in str(excinfo.value)


def test_chown_tree_creates_missing_dir(tmp_path: Path) -> None:
    target = tmp_path / "state"
    entrypoint._chown_tree(str(target), os.getuid(), os.getgid())
    assert target.is_dir()


def test_chown_tree_walks_existing_contents(tmp_path: Path) -> None:
    target = tmp_path / "state"
    (target / "sub").mkdir(parents=True)
    (target / "sub" / "enfilera.db").write_text("x")
    # Chowning to the current uid/gid is permitted without root and exercises
    # the recursive walk over nested contents without changing anything.
    entrypoint._chown_tree(str(target), os.getuid(), os.getgid())
    assert (target / "sub" / "enfilera.db").read_text() == "x"
