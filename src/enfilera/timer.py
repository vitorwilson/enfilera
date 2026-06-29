"""Pure timer math for the "register time" flow.

The elapsed transit time is the gap between two *server* timestamps (start at
the back of the queue, stop at the turnstile) — never the device clock, so a
user cannot fabricate a duration (docs/PLAN.md §3). ``classify_elapsed`` then
applies the physical clamp: too short is discarded, too long is rejected as
implausible, the rest is accepted for storage.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from enfilera.estimation_config import EstimationConfig


class ElapsedVerdict(Enum):
    """Outcome of validating a measured transit time against the clamp."""

    ACCEPTED = "accepted"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"


def elapsed_seconds(start: datetime, stop: datetime) -> int:
    """Whole seconds between two timezone-aware server timestamps.

    >>> from datetime import UTC, datetime
    >>> elapsed_seconds(
    ...     datetime(2026, 6, 30, 12, 0, tzinfo=UTC),
    ...     datetime(2026, 6, 30, 12, 12, 30, tzinfo=UTC))
    750
    """
    if start.tzinfo is None or stop.tzinfo is None:
        raise ValueError(f"start and stop must be timezone-aware, got {start!r}")
    delta = (stop - start).total_seconds()
    if delta < 0:
        raise ValueError(f"stop {stop!r} precedes start {start!r}")
    return int(delta)


def classify_elapsed(seconds: int, config: EstimationConfig) -> ElapsedVerdict:
    """Classify a measured transit time against the configured clamp band."""
    if seconds < config.clamp_min:
        return ElapsedVerdict.TOO_SHORT
    if seconds > config.clamp_max:
        return ElapsedVerdict.TOO_LONG
    return ElapsedVerdict.ACCEPTED
