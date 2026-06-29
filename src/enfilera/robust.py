"""Robust statistics primitives for the estimator.

Pure numeric helpers with no domain knowledge. The estimator summarizes
transit-time samples with these so a *minority* of poisoned values cannot
move the result (docs/PLAN.md §2.5). The arithmetic mean is deliberately
absent here: a single liar ruins it.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import fmean, median

MAX_TRIM_PROPORTION = 0.5


def median_of(values: Sequence[float]) -> float:
    """Median of a non-empty sequence.

    >>> median_of([5, 1, 3])
    3
    """
    if not values:
        raise ValueError("median_of needs at least one value, got []")
    return median(values)


def mad(values: Sequence[float], center: float) -> float:
    """Median absolute deviation of ``values`` about ``center``.

    A spread measure that, like the median, shrugs off a minority of
    outliers (the 88 below moves the mean but not this).

    >>> mad([10, 12, 14], center=12)
    2
    """
    if not values:
        raise ValueError("mad needs at least one value, got []")
    return median([abs(value - center) for value in values])


def trimmed_mean(values: Sequence[float], proportion: float) -> float:
    """Mean after dropping ``proportion`` of the values from each tail.

    ``proportion < 0.5`` keeps at least the middle value, so the result is
    always defined for a non-empty input. With small n the cut rounds down
    to zero and nothing is dropped.

    >>> trimmed_mean([1, 2, 3, 4, 100], 0.2)
    3.0
    """
    if not values:
        raise ValueError("trimmed_mean needs at least one value, got []")
    if not 0 <= proportion < MAX_TRIM_PROPORTION:
        raise ValueError(
            f"proportion must be in [0, {MAX_TRIM_PROPORTION}), got {proportion!r}"
        )
    ordered = sorted(values)
    cut = int(len(ordered) * proportion)
    return fmean(ordered[cut : len(ordered) - cut])
