"""Tests for assembling the full AppConfig from the TOML file.

Builds from the shipped example config, so this doubles as a check that the
committed ``config.example.toml`` stays valid as sections evolve.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from enfilera.config_loader import AppConfig, build_config, load_config

EXAMPLE = Path(__file__).resolve().parent.parent / "config" / "config.example.toml"


def _raw() -> dict:
    with open(EXAMPLE, "rb") as handle:
        return tomllib.load(handle)


def test_build_config_assembles_every_section() -> None:
    config = build_config(_raw())
    assert config.bot.token_env == "ENFILERA_BOT_TOKEN"
    assert len(config.lines) == 3
    assert config.geofence.radius_m == 50
    assert config.estimation.min_samples == 3
    assert config.estimation.clamp_max == 3600  # 60 min → seconds
    assert config.retention_days == 30
    assert str(config.schedule.timezone) == "America/Sao_Paulo"


def test_load_config_reads_the_example_file() -> None:
    config = load_config(EXAMPLE)
    assert isinstance(config, AppConfig)
    assert config.bot.token_env == "ENFILERA_BOT_TOKEN"


def test_missing_section_raises_naming_it(tmp_path: Path) -> None:
    incomplete = tmp_path / "config.toml"
    incomplete.write_text('[restaurant]\nname = "x"\n')  # no [bot] section
    with pytest.raises(ValueError, match=r"\[bot\]"):
        load_config(incomplete)
