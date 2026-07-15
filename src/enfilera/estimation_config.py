"""Static estimation parameters parsed from the ``[estimation]`` config.

Durations are written in *minutes* in the file (what a forker reasons about)
and converted to *seconds* here — the unit the estimator works in end to end.
A stopwatch measures seconds and storing whole seconds avoids float drift, so
seconds is the canonical unit; only the config edge speaks minutes. ``mad_k``
and ``min_samples`` are unitless.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from enfilera.config_parsing import (
    non_negative_int,
    positive_int,
    positive_number,
    section,
)

SECONDS_PER_MINUTE = 60


@dataclass(frozen=True)
class EstimationConfig:
    """Validated estimator parameters. All durations are in seconds."""

    min_samples: int
    clamp_min: int  # seconds; samples below are discarded
    clamp_max: int  # seconds; samples above are discarded
    mad_k: float  # outlier band half-width, in multiples of the baseline MAD


def build_estimation_config(raw: Mapping[str, object]) -> EstimationConfig:
    """Parse and validate the ``[estimation]`` section (minutes → seconds).

    >>> build_estimation_config({"estimation": {
    ...     "min_samples": 3, "clamp_min_minutes": 0,
    ...     "clamp_max_minutes": 60, "mad_k": 3.0,
    ... }}).clamp_max
    3600
    """
    est = section(raw, "estimation")
    clamp_min = _floor_minutes_to_seconds(est["clamp_min_minutes"])
    clamp_max = _minutes_to_seconds(est["clamp_max_minutes"], "clamp_max_minutes")
    if clamp_min >= clamp_max:
        raise ValueError(
            f"clamp_min must be below clamp_max, got {clamp_min}s..{clamp_max}s"
        )
    return EstimationConfig(
        min_samples=positive_int(est["min_samples"], "min_samples"),
        clamp_min=clamp_min,
        clamp_max=clamp_max,
        mad_k=positive_number(est["mad_k"], "mad_k"),
    )


def _minutes_to_seconds(value: object, field: str) -> int:
    return positive_int(value, field) * SECONDS_PER_MINUTE


def _floor_minutes_to_seconds(value: object) -> int:
    # The lower clamp allows 0: a zero-minute floor keeps genuine empty-line
    # waits (sub-minute transits) instead of discarding them as "too short".
    return non_negative_int(value, "clamp_min_minutes") * SECONDS_PER_MINUTE
