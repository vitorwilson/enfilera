"""Sample-admission pipeline: physical clamp + relative outlier rejection.

Turns a block's raw transit-time samples (seconds) into the subset trusted
for aggregation. Two gates, in order (docs/PLAN.md §2.4):

1. **Physical clamp** — discard anything outside the configured
   ``[clamp_min, clamp_max]`` band. After the geofence, this ceiling is the
   single highest-leverage poison defense.
2. **Relative outlier rejection** — discard anything more than ``k·MAD`` from
   the *historical* baseline for that (line, weekday, block). The band is
   built from stable history, NEVER from today's live samples; otherwise the
   first (possibly poisoned) value of the day would define its own
   plausibility.

With no trustworthy history yet (fresh fork, sparse bucket) only the clamp
applies — we never invent a rejection band out of today's own data. Blending
today's live spread in once the block has enough honest samples is a
documented future refinement (docs/PLAN.md §2.4), deliberately out of v0.1.

Callers pass already-validated history to ``compute_baseline``: stored samples
were clamped at write time, so the baseline is not re-clamped here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from enfilera.estimation_config import EstimationConfig
from enfilera.robust import mad, median_of


@dataclass(frozen=True)
class Baseline:
    """Robust center + spread of a (line, weekday, block) bucket's history.

    ``spread`` is the median absolute deviation (seconds). This is the
    reference for outlier rejection and the confidence-gating seed — never a
    band derived from today's live samples.
    """

    center: float  # seconds
    spread: float  # seconds (MAD about center)


def compute_baseline(
    historical: Sequence[int], config: EstimationConfig
) -> Baseline | None:
    """Robust baseline from a bucket's rolling raw samples, else ``None``.

    Returns ``None`` below ``min_samples`` historical samples: too little
    history to judge an outlier reliably (the tiny-n guard), so callers fall
    back to clamp-only admission rather than rejecting against noise.

    >>> from enfilera.estimation_config import EstimationConfig
    >>> cfg = EstimationConfig(3, 60, 3600, 3.0)
    >>> compute_baseline([600, 660, 720], cfg)
    Baseline(center=660, spread=60)
    """
    if len(historical) < config.min_samples:
        return None
    center = median_of(historical)
    return Baseline(center=center, spread=mad(historical, center))


def admit_samples(
    raw: Sequence[int], baseline: Baseline | None, config: EstimationConfig
) -> list[int]:
    """The samples passing the clamp and, when available, the baseline band.

    The baseline band is skipped when there is no baseline or its spread is
    zero: a zero-MAD history gives no scale to judge deviation, and the clamp
    still rejects absurd values (the MAD = 0 guard).

    >>> from enfilera.estimation_config import EstimationConfig
    >>> cfg = EstimationConfig(3, 60, 3600, 3.0)
    >>> admit_samples([30, 600, 660, 720, 5000], Baseline(660, 60), cfg)
    [600, 660, 720]
    """
    clamped = [s for s in raw if config.clamp_min <= s <= config.clamp_max]
    if baseline is None or baseline.spread == 0:
        return clamped
    width = config.mad_k * baseline.spread
    return [s for s in clamped if abs(s - baseline.center) <= width]
