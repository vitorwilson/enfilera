"""Tests for parsing the ``[estimation]`` config section.

The key behaviour beyond validation is the minutes → seconds conversion:
the file speaks minutes (forker-friendly), the estimator speaks seconds.
"""

import pytest

from enfilera.estimation_config import build_estimation_config


def _raw(**overrides: object) -> dict:
    estimation = {
        "min_samples": 3,
        "clamp_min_minutes": 1,
        "clamp_max_minutes": 60,
        "mad_k": 3.0,
    }
    estimation.update(overrides)
    return {"estimation": estimation}


# --- happy path: parsing + minutes->seconds ------------------------------


def test_parses_and_converts_minutes_to_seconds() -> None:
    config = build_estimation_config(_raw())

    assert config.min_samples == 3
    assert config.clamp_min == 60
    assert config.clamp_max == 3600
    assert config.mad_k == 3.0


def test_accepts_integer_mad_k() -> None:
    assert build_estimation_config(_raw(mad_k=2)).mad_k == 2.0


# --- validation ----------------------------------------------------------


def test_rejects_missing_section() -> None:
    with pytest.raises(ValueError, match=r"\[estimation\]"):
        build_estimation_config({})


def test_rejects_clamp_min_not_below_max() -> None:
    with pytest.raises(ValueError, match="clamp_min must be below clamp_max"):
        build_estimation_config(_raw(clamp_min_minutes=60, clamp_max_minutes=60))


def test_rejects_zero_min_samples() -> None:
    with pytest.raises(ValueError, match="min_samples"):
        build_estimation_config(_raw(min_samples=0))


def test_rejects_bool_min_samples() -> None:
    with pytest.raises(ValueError, match="min_samples"):
        build_estimation_config(_raw(min_samples=True))


def test_rejects_non_positive_mad_k() -> None:
    with pytest.raises(ValueError, match="mad_k"):
        build_estimation_config(_raw(mad_k=0))


def test_accepts_zero_clamp_min() -> None:
    # A zero-minute lower clamp keeps genuine empty-line waits (sub-minute
    # transits) instead of discarding them as "too short".
    assert build_estimation_config(_raw(clamp_min_minutes=0)).clamp_min == 0


def test_rejects_negative_clamp_min() -> None:
    with pytest.raises(ValueError, match="clamp_min_minutes"):
        build_estimation_config(_raw(clamp_min_minutes=-1))
