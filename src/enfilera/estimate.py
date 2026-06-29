"""Resolve a single displayed estimate for one (line, weekday, block).

The orchestration layer (docs/PLAN.md §2.6): admit today's samples, and when
the block holds enough honest ones, aggregate them robustly. Otherwise walk
the confidence-fallback chain — previous block today → historical seed →
configured default — so the bot always has one number to show. The user sees
it formatted as "~N min".
"""

from __future__ import annotations

from collections.abc import Sequence

from enfilera.estimation_config import EstimationConfig
from enfilera.robust import median_of, trimmed_mean
from enfilera.validity import Baseline, admit_samples

# Aggregate choice by sample count (docs/PLAN.md §2.5): the median is steadiest
# for very small n; past this many samples a 20% trimmed mean uses more of the
# data while still discarding both tails.
MEDIAN_MAX_N = 5
TRIM_PROPORTION = 0.2

# Never show "~0 min": the smallest wait we report is one minute.
MIN_DISPLAY_MINUTES = 1
SECONDS_PER_MINUTE = 60


def robust_aggregate(samples: Sequence[int]) -> float:
    """Median for small n, 20% trimmed mean for larger n (seconds in/out).

    >>> robust_aggregate([600, 660, 720])
    660
    >>> robust_aggregate([1, 600, 660, 690, 720, 9000])
    667.5
    """
    if not samples:
        raise ValueError("robust_aggregate needs at least one sample, got []")
    if len(samples) <= MEDIAN_MAX_N:
        return median_of(samples)
    return trimmed_mean(samples, TRIM_PROPORTION)


def estimate_seconds(
    today: Sequence[int],
    baseline: Baseline | None,
    previous_block: int | None,
    config: EstimationConfig,
) -> int:
    """The estimate (seconds) for one bucket, via gating + fallback chain.

    ``previous_block`` is the already-resolved estimate of the prior block
    today (``None`` at a period's first block); ``baseline`` is the
    *historical* reference for this bucket (``None`` with too little history).
    When today's admitted samples reach ``min_samples`` they win; otherwise:
    previous block → historical seed (baseline center) → configured default.
    """
    admitted = admit_samples(today, baseline, config)
    if len(admitted) >= config.min_samples:
        return round(robust_aggregate(admitted))
    if previous_block is not None:
        return previous_block
    if baseline is not None:
        return round(baseline.center)
    return config.default_seed


def format_estimate(seconds: int) -> str:
    """Render an estimate (seconds) as the single user-facing string.

    >>> format_estimate(725)
    '~12 min'
    >>> format_estimate(20)
    '~1 min'
    """
    minutes = max(MIN_DISPLAY_MINUTES, round(seconds / SECONDS_PER_MINUTE))
    return f"~{minutes} min"
