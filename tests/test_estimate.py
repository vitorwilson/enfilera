"""Tests for the estimate orchestration: gating, aggregation, formatting.

Most of Feature 2's risk lands here, so this is the densest test file. All
durations are seconds; the default config is min_samples=3, default_seed=60s,
clamp [60s, 3600s], k=3. The adversarial block at the bottom covers the
threat model from docs/PLAN.md §2–3: minority poison is rejected, but a
malicious *majority* inside the band is explicitly not survivable (that is
what the geofence + one-per-period rule exist to prevent).
"""

import pytest

from enfilera.estimate import (
    estimate_seconds,
    format_estimate,
    robust_aggregate,
)
from enfilera.estimation_config import EstimationConfig
from enfilera.validity import Baseline


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


# --- robust_aggregate: median (small n) vs trimmed mean (larger n) --------


def test_aggregate_small_n_uses_median() -> None:
    assert robust_aggregate([600, 660, 720]) == 660


def test_aggregate_larger_n_uses_trimmed_mean() -> None:
    # n=6 -> trim 1 each end of sorted, mean of [600, 660, 700, 720] = 670
    assert robust_aggregate([300, 600, 660, 700, 720, 3000]) == 670.0


def test_aggregate_empty_raises() -> None:
    with pytest.raises(ValueError, match="robust_aggregate"):
        robust_aggregate([])


# --- estimate_seconds: enough honest samples win -------------------------


def test_enough_samples_returns_robust_aggregate() -> None:
    estimate = estimate_seconds([600, 660, 720], None, None, _config())
    assert estimate == 660


def test_all_identical_samples_return_that_value() -> None:
    assert estimate_seconds([600, 600, 600], None, None, _config()) == 600


# --- estimate_seconds: confidence-fallback chain -------------------------


def test_sparse_block_falls_back_to_previous_block() -> None:
    estimate = estimate_seconds([600], Baseline(900, 60), 540, _config())
    assert estimate == 540


def test_sparse_block_no_previous_falls_back_to_historical_seed() -> None:
    estimate = estimate_seconds([600], Baseline(900, 60), None, _config())
    assert estimate == 900


def test_sparse_block_no_history_falls_back_to_default_seed() -> None:
    assert estimate_seconds([600], None, None, _config()) == 60


def test_first_sample_of_day_with_no_history_is_default_seed() -> None:
    # The fresh-fork bootstrap: nothing anywhere -> the configured default.
    assert estimate_seconds([], None, None, _config()) == 60


def test_previous_block_preferred_over_historical_seed() -> None:
    # Both available; the more-recent previous block wins (docs/PLAN.md §2.6).
    estimate = estimate_seconds([], Baseline(900, 60), 540, _config())
    assert estimate == 540


# --- format_estimate -----------------------------------------------------


def test_format_rounds_to_minutes() -> None:
    assert format_estimate(725) == "~12 min"


def test_format_floors_at_one_minute() -> None:
    assert format_estimate(20) == "~1 min"
    assert format_estimate(0) == "~1 min"


def test_format_default_seed_is_one_minute() -> None:
    assert format_estimate(60) == "~1 min"


# --- adversarial: minority poison rejected, majority not survivable -------


def test_minority_high_poison_does_not_move_estimate() -> None:
    baseline = Baseline(660, 60)  # band [480, 840]
    estimate = estimate_seconds([600, 660, 720, 3000], baseline, None, _config())
    assert estimate == 660  # the 3000 was rejected before aggregation


def test_minority_low_poison_does_not_move_estimate() -> None:
    baseline = Baseline(660, 60)  # band [480, 840]
    estimate = estimate_seconds([120, 600, 660, 720], baseline, None, _config())
    assert estimate == 660  # the 120 was rejected before aggregation


def test_poison_outside_band_can_drop_block_below_quorum() -> None:
    # Enough poison rejected that the honest remainder is sub-quorum: we fall
    # back rather than aggregate two lonely samples.
    baseline = Baseline(660, 60)  # band [480, 840]
    estimate = estimate_seconds([600, 660, 3000, 3000], baseline, 540, _config())
    assert estimate == 540


def test_malicious_majority_inside_band_is_not_survivable() -> None:
    # Documents the boundary: poison that stays within the historical band and
    # outnumbers honest samples DOES move the median. No estimator survives a
    # majority; the geofence + one-per-period rule keep attackers a minority.
    baseline = Baseline(660, 60)  # band [480, 840]
    estimate = estimate_seconds([800, 800, 800, 600, 660], baseline, None, _config())
    assert estimate == 800
