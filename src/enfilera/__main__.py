"""Entry point: ``python -m enfilera`` runs the bot from config + env.

The static config path and the SQLite file default to repo-relative locations
and can be overridden with the ``ENFILERA_CONFIG`` / ``ENFILERA_DB`` environment
variables; the bot token is read from the env var named in the config.
"""

from __future__ import annotations

import os

from enfilera import app

_DEFAULT_CONFIG = "config/config.toml"
_DEFAULT_DB = "enfilera.db"


def main() -> None:
    """Resolve paths from the environment and start the bot."""
    app.run(
        os.environ.get("ENFILERA_CONFIG", _DEFAULT_CONFIG),
        os.environ,
        os.environ.get("ENFILERA_DB", _DEFAULT_DB),
    )


if __name__ == "__main__":
    main()
