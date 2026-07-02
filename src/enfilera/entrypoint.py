"""Container entrypoint: fix the data-volume owner, then drop privileges.

Compose bind-mounts ``./data`` over ``/app/data``. On a rootful Docker host a
missing ``./data`` is created by the daemon as ``root:root``; the unprivileged
``app`` user (UID 1000) then cannot write it and the SQLite database fails to
open on first run. So the image keeps root as its entry user, this shim chowns
the mounted data directory to ``app`` and re-execs the real command as that
user. Started already-unprivileged (``docker run --user 1000``) it skips the
chown — the operator has taken ownership into their own hands — and execs
directly.

Runs as ``python -m enfilera.entrypoint <command...>`` where ``<command...>``
is the Docker ``CMD`` (the bot) or the compose ``command`` override (the prune
loop):

    python -m enfilera.entrypoint python -m enfilera
"""

from __future__ import annotations

import os
import pwd
import sys
from collections.abc import Callable, Mapping, Sequence

_APP_USER = "app"
_DEFAULT_DB = "/app/data/enfilera.db"


def data_dir(environ: Mapping[str, str]) -> str:
    """Directory that must be writable by the app user — where the DB lives.

    Derived from ``ENFILERA_DB`` so overriding the database path moves the
    chown target with it.

    >>> data_dir({"ENFILERA_DB": "/srv/enfilera/state/db.sqlite"})
    '/srv/enfilera/state'
    """
    return os.path.dirname(environ.get("ENFILERA_DB", _DEFAULT_DB))


def main(
    argv: Sequence[str],
    environ: Mapping[str, str],
    is_root: Callable[[], bool],
    take_ownership: Callable[[str], None],
    exec_command: Callable[[Sequence[str]], None],
) -> None:
    """Chown the data volume and drop privileges (only when root), then exec.

    Side effects are injected so the branch logic is unit-testable without
    actually being root: ``is_root`` reports the effective UID, ``take_ownership``
    chowns the data dir and drops to ``app``, ``exec_command`` replaces this
    process with the target command.
    """
    command = argv[1:]
    if not command:
        raise SystemExit(
            f"entrypoint: no command to exec; got argv={list(argv)!r}, "
            "expected the target command after the script name"
        )
    if is_root():
        take_ownership(data_dir(environ))
    exec_command(command)


def _take_ownership(directory: str) -> None:
    """Give the data dir to ``app`` and drop this process to that user."""
    user = pwd.getpwnam(_APP_USER)
    _chown_tree(directory, user.pw_uid, user.pw_gid)
    _drop_privileges(user)


def _chown_tree(directory: str, uid: int, gid: int) -> None:
    os.makedirs(directory, exist_ok=True)
    os.chown(directory, uid, gid)
    for parent, dirs, files in os.walk(directory):
        for name in (*dirs, *files):
            os.chown(os.path.join(parent, name), uid, gid)


def _drop_privileges(user: pwd.struct_passwd) -> None:
    # gid before uid: once the uid is dropped we can no longer change the gid.
    os.initgroups(user.pw_name, user.pw_gid)
    os.setgid(user.pw_gid)
    os.setuid(user.pw_uid)


def run() -> None:
    """Wire the real OS side effects and run (the module ``__main__``)."""
    main(
        sys.argv,
        os.environ,
        is_root=lambda: os.geteuid() == 0,
        take_ownership=_take_ownership,
        exec_command=lambda command: os.execvp(command[0], list(command)),
    )


if __name__ == "__main__":
    run()
