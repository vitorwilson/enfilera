"""Tests for the sample-admission pipeline and historical baseline.

Samples are transit times in seconds. The default config band is
[60s, 3600s] with k=3 against a historical MAD. Adversarial cases (minority
poison high and low, all-identical history, first-sample-of-day) live here —
this is the layer that decides which numbers the estimator is even allowed to
see.
"""

from enfilera.estimation_config import EstimationConfig
from enfilera.validity import Baseline, admit_samples, compute_baseline


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


# --- compute_baseline ----------------------------------------------------


def test_baseline_center_and_spread() -> None:
    baseline = compute_baseline([600, 660, 720], _config())
    assert baseline == Baseline(center=660, spread=60)


def test_baseline_none_below_min_samples() -> None:
    # Two historical samples is too little to judge an outlier against.
    assert compute_baseline([600, 660], _config(min_samples=3)) is None


def test_baseline_spread_zero_for_identical_history() -> None:
    baseline = compute_baseline([600, 600, 600], _config())
    assert baseline == Baseline(center=600, spread=0)


# --- admit_samples: physical clamp ---------------------------------------


def test_clamp_discards_below_floor() -> None:
    # 30s is under the 1-minute floor; the rest pass (no baseline).
    assert admit_samples([30, 600, 700], None, _config()) == [600, 700]


def test_clamp_discards_above_ceiling() -> None:
    # 5000s (~83 min) is over the 60-minute ceiling.
    assert admit_samples([600, 700, 5000], None, _config()) == [600, 700]


def test_clamp_boundaries_are_inclusive() -> None:
    assert admit_samples([60, 3600], None, _config()) == [60, 3600]


# --- admit_samples: relative outlier rejection ---------------------------


def test_rejects_high_minority_poison_against_baseline() -> None:
    baseline = Baseline(center=660, spread=60)  # band 660 ± 180 = [480, 840]
    assert admit_samples([600, 660, 720, 3000], baseline, _config()) == [
        600,
        660,
        720,
    ]


def test_rejects_low_minority_poison_against_baseline() -> None:
    baseline = Baseline(center=660, spread=60)  # band [480, 840]
    # 120s passes the clamp but is far below the historical band.
    assert admit_samples([120, 600, 660, 720], baseline, _config()) == [
        600,
        660,
        720,
    ]


def test_band_uses_historical_center_not_todays_samples() -> None:
    # Today is dominated by a high cluster, but the band is anchored to the
    # historical center, so the high cluster is what gets rejected.
    baseline = Baseline(center=660, spread=60)  # band [480, 840]
    assert admit_samples([2000, 2010, 2020, 700], baseline, _config()) == [700]


def test_mad_zero_baseline_skips_rejection() -> None:
    # Zero-spread history gives no scale; only the clamp filters.
    baseline = Baseline(center=600, spread=0)
    assert admit_samples([120, 600, 3000], baseline, _config()) == [120, 600, 3000]


def test_no_baseline_applies_clamp_only() -> None:
    # First samples of the day with no history: clamp only, no band invented.
    assert admit_samples([120, 600, 3000], None, _config()) == [120, 600, 3000]


def test_wider_k_admits_more() -> None:
    baseline = Baseline(center=660, spread=60)  # k=6 -> band [300, 1020]
    assert admit_samples([960, 1000], baseline, _config(mad_k=6.0)) == [960, 1000]


def test_empty_input_yields_empty() -> None:
    assert admit_samples([], Baseline(660, 60), _config()) == []
