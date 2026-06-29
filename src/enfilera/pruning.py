"""The scheduled pruning job: keep the database bounded.

Drops raw samples past the retention window and closure records whose date
has already passed, so a long-running install's SQLite file does not grow
without bound (docs/PLAN.md §3). Pure orchestration over the stores; the
caller supplies timezone-aware server time and the retention window from
config. Closures are kept through the whole of their own day (cutoff is the
local date), so a closure never expires mid-day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from enfilera.closures_store import ClosureStore
from enfilera.samples_store import SampleStore


@dataclass(frozen=True)
class PruneResult:
    """How many rows each step removed, for the operator log."""

    samples_removed: int
    closures_removed: int


def run_pruning(
    samples: SampleStore,
    closures: ClosureStore,
    now: datetime,
    retention_days: int,
) -> PruneResult:
    """Prune samples older than ``retention_days`` and already-past closures.

    >>> # Wiring only; see tests/test_pruning.py for behaviour over a real DB.
    """
    if retention_days <= 0:
        raise ValueError(f"retention_days must be positive, got {retention_days}")
    sample_cutoff = now - timedelta(days=retention_days)
    return PruneResult(
        samples_removed=samples.prune_older_than(sample_cutoff),
        closures_removed=closures.prune_before(now.date()),
    )
