"""Tests for the robust statistics primitives.

The whole point of these helpers is resistance to a minority of poisoned
values, so most cases inject an extreme outlier and assert it barely moves
(or doesn't move) the result.
"""

import pytest

from enfilera.robust import mad, median_of, trimmed_mean

# --- median_of -----------------------------------------------------------


def test_median_odd_count() -> None:
    assert median_of([5, 1, 3]) == 3


def test_median_even_count_averages_middle() -> None:
    assert median_of([1, 2, 3, 4]) == 2.5


def test_median_ignores_single_high_outlier() -> None:
    assert median_of([10, 11, 12, 9000]) == 11.5


def test_median_empty_raises() -> None:
    with pytest.raises(ValueError, match="median_of"):
        median_of([])


# --- mad -----------------------------------------------------------------


def test_mad_about_center() -> None:
    # deviations [2, 0, 2] -> median 2
    assert mad([10, 12, 14], center=12) == 2


def test_mad_unmoved_by_minority_outlier() -> None:
    # deviations [2, 0, 2, 88] -> median 2 (the 88 sits in the tail)
    assert mad([10, 12, 14, 100], center=12) == 2


def test_mad_zero_when_all_identical() -> None:
    assert mad([12, 12, 12], center=12) == 0


def test_mad_empty_raises() -> None:
    with pytest.raises(ValueError, match="mad"):
        mad([], center=0)


# --- trimmed_mean --------------------------------------------------------


def test_trimmed_mean_drops_both_tails() -> None:
    # n=5, 20% -> cut 1 each end, keep [2, 3, 4]
    assert trimmed_mean([1, 2, 3, 4, 100], 0.2) == 3.0


def test_trimmed_mean_resists_high_and_low_poison() -> None:
    assert trimmed_mean([0, 10, 11, 12, 9000], 0.2) == 11.0


def test_trimmed_mean_zero_proportion_is_plain_mean() -> None:
    assert trimmed_mean([1, 2, 3, 4], 0.0) == 2.5


def test_trimmed_mean_small_n_drops_nothing() -> None:
    # n=2, 20% -> cut rounds down to 0, nothing dropped
    assert trimmed_mean([2, 4], 0.2) == 3.0


def test_trimmed_mean_empty_raises() -> None:
    with pytest.raises(ValueError, match="trimmed_mean"):
        trimmed_mean([], 0.2)


@pytest.mark.parametrize("bad", [0.5, 0.9, -0.1])
def test_trimmed_mean_rejects_out_of_range_proportion(bad: float) -> None:
    with pytest.raises(ValueError, match="proportion"):
        trimmed_mean([1, 2, 3], bad)
