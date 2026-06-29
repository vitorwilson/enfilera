"""The pruning entrypoint: ``python -m enfilera.prune``.

The bot process runs no scheduler (PTB's JobQueue is disabled in ``bot.py``),
so the retention job that keeps the SQLite file bounded (docs/PLAN.md §3) runs
as its own short-lived command. The ``prune`` sidecar in ``compose.yaml`` runs
it once a day, so pruning ships with the deploy (no host cron); you can also run
it on demand with ``docker compose run --rm enfilera python -m enfilera.prune``.
It loads the same static config and database as the bot, prunes, logs the counts
as one JSON line, and exits.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from enfilera.closures_store import ClosureStore
from enfilera.config_loader import load_config
from enfilera.db import connect
from enfilera.json_logging import configure_logging
from enfilera.pruning import PruneResult, run_pruning
from enfilera.samples_store import SampleStore

_logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = "config/config.toml"
_DEFAULT_DB = "enfilera.db"


def run(config_path: str | Path, db_path: str, now: datetime) -> PruneResult:
    """Load config + database, prune past-retention rows, and log the counts."""
    config = load_config(config_path)
    conn = connect(db_path)
    try:
        result = run_pruning(
            SampleStore(conn), ClosureStore(conn), now, config.retention_days
        )
    finally:
        conn.close()
    _logger.info(
        "pruning complete",
        extra={
            "samples_removed": result.samples_removed,
            "closures_removed": result.closures_removed,
        },
    )
    return result


def main(
    env: Mapping[str, str] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> None:
    """Resolve paths from the environment and run one pruning pass."""
    resolved = os.environ if env is None else env
    configure_logging()
    run(
        resolved.get("ENFILERA_CONFIG", _DEFAULT_CONFIG),
        resolved.get("ENFILERA_DB", _DEFAULT_DB),
        now(),
    )


if __name__ == "__main__":
    main()
