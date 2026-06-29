"""Tests for the pure timer math."""

from datetime import UTC, datetime, timedelta

import pytest

from enfilera.estimation_config import EstimationConfig
from enfilera.timer import ElapsedVerdict, classify_elapsed, elapsed_seconds

START = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)


def _config(**overrides: object) -> EstimationConfig:
    defaults = {
        "min_samples": 3,
        "default_seed": 60,
        "clamp_min": 60,
        "clamp_max": 3600,
        "mad_k": 3.0,
    }
    defaults.update(overrides)
    return EstimationConfig(**defaults)  # type: ignore[arg-type]


# --- elapsed_seconds -----------------------------------------------------


def test_elapsed_seconds_truncates_to_whole_seconds() -> None:
    assert elapsed_seconds(START, START + timedelta(seconds=750.9)) == 750


def test_elapsed_rejects_stop_before_start() -> None:
    with pytest.raises(ValueError, match="precedes start"):
        elapsed_seconds(START, START - timedelta(seconds=1))


def test_elapsed_rejects_naive() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        elapsed_seconds(datetime(2026, 6, 30, 12, 0), START)


# --- classify_elapsed ----------------------------------------------------


def test_below_floor_is_too_short() -> None:
    assert classify_elapsed(59, _config()) == ElapsedVerdict.TOO_SHORT


def test_at_floor_is_accepted() -> None:
    assert classify_elapsed(60, _config()) == ElapsedVerdict.ACCEPTED


def test_within_band_is_accepted() -> None:
    assert classify_elapsed(720, _config()) == ElapsedVerdict.ACCEPTED


def test_at_ceiling_is_accepted() -> None:
    assert classify_elapsed(3600, _config()) == ElapsedVerdict.ACCEPTED


def test_above_ceiling_is_too_long() -> None:
    assert classify_elapsed(3601, _config()) == ElapsedVerdict.TOO_LONG
