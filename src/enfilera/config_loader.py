"""Load and assemble the full static configuration from one TOML file.

Reads the file once and runs every section builder into a single frozen
``AppConfig`` the composition root wires the bot from. A forker edits the file;
if any required value is missing or malformed, the relevant builder raises here
at startup — before the bot connects — naming the offending field. The bot
token is *not* part of this: it comes from the environment (see ``BotConfig``).
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from enfilera.bot_config import BotConfig, build_bot_config
from enfilera.config_parsing import positive_int, section
from enfilera.estimation_config import EstimationConfig, build_estimation_config
from enfilera.geofence import Geofence, build_geofence
from enfilera.lines import Line, build_lines
from enfilera.schedule import Schedule, build_schedule


@dataclass(frozen=True)
class AppConfig:
    """Every static config object, assembled from one TOML file."""

    bot: BotConfig
    schedule: Schedule
    geofence: Geofence
    estimation: EstimationConfig
    lines: tuple[Line, ...]
    retention_days: int
    backup_keep: int


def build_config(raw: dict) -> AppConfig:
    """Assemble an ``AppConfig`` from an already-parsed config mapping."""
    return AppConfig(
        bot=build_bot_config(raw),
        schedule=build_schedule(raw),
        geofence=build_geofence(raw),
        estimation=build_estimation_config(raw),
        lines=build_lines(raw),
        retention_days=_retention_days(raw),
        backup_keep=_backup_keep(raw),
    )


def load_config(path: str | Path) -> AppConfig:
    """Read and assemble the config TOML at ``path``."""
    with open(path, "rb") as handle:
        raw = tomllib.load(handle)
    return build_config(raw)


def _retention_days(raw: dict) -> int:
    retention = section(raw, "retention")
    return positive_int(retention["sample_days"], "sample_days")


# Backups are optional config: a fork (or the already-deployed install) that
# never adds a [backup] section still gets automatic backups at this default,
# so shipping the feature can't break a config written before it existed.
_DEFAULT_BACKUP_KEEP = 30


def _backup_keep(raw: dict) -> int:
    backup = raw.get("backup")
    if not isinstance(backup, Mapping) or "keep" not in backup:
        return _DEFAULT_BACKUP_KEEP
    return positive_int(backup["keep"], "keep")
