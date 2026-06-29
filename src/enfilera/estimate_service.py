"""Turn stored samples into the live estimate for a line, right now.

This is the consumer that wires Feature 3 (the sample store) into Feature 2
(the pure estimator). For the user's current block it walks the blocks of the
current period from the period's start, resolving each block's estimate and
carrying it forward as the ``previous_block`` fallback — exactly the chain the
estimator expects (docs/PLAN.md §2.6). The historical baseline for each block
is read from the same weekday over the retention window and, crucially, stops
at the start of today so today's live data never anchors its own outlier band.

Dependencies (sample store, schedule, config) are injected; this service holds
no I/O of its own beyond the store it is given.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from enfilera.estimate import estimate_seconds
from enfilera.estimation_config import EstimationConfig
from enfilera.samples_store import SampleStore
from enfilera.schedule import (
    Block,
    Period,
    Schedule,
    block_for,
    period_containing,
    previous_block,
)
from enfilera.validity import compute_baseline


class EstimationService:
    """Resolve a line's current estimate from stored samples and server time."""

    def __init__(
        self,
        samples: SampleStore,
        schedule: Schedule,
        config: EstimationConfig,
        retention_days: int,
    ) -> None:
        self._samples = samples
        self._schedule = schedule
        self._config = config
        self._retention_days = retention_days

    def current_estimate(self, now: datetime, line_id: str) -> int | None:
        """Estimate (seconds) for ``line_id`` at ``now``, or ``None`` if closed.

        ``None`` means ``now`` falls outside every operating period; the caller
        already knows the open/closed status and shows the closed message.
        """
        local = now.astimezone(self._schedule.timezone)
        period = period_containing(local.time(), self._schedule)
        if period is None:
            return None
        today_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        weekday = local.isoweekday()
        current = block_for(local.time(), self._schedule)
        estimate: int | None = None
        # Resolve blocks in order, carrying each result forward as the next
        # block's previous-block fallback (docs/PLAN.md §2.6).
        for block in self._blocks_until(current, period):
            estimate = self._estimate_block(
                line_id, weekday, block, today_start, estimate
            )
        return estimate

    def _estimate_block(
        self,
        line_id: str,
        weekday: int,
        block: Block,
        today_start: datetime,
        previous: int | None,
    ) -> int:
        history_since = today_start - timedelta(days=self._retention_days)
        historical = self._samples.values_in_window(
            line_id, weekday, block.start, history_since, until=today_start
        )
        today = self._samples.values_in_window(
            line_id, weekday, block.start, today_start
        )
        baseline = compute_baseline(historical, self._config)
        return estimate_seconds(today, baseline, previous, self._config)

    def _blocks_until(self, current: Block, period: Period) -> list[Block]:
        """The period's blocks from its start through ``current``, in order."""
        blocks = [current]
        earlier = previous_block(current, period, self._schedule)
        while earlier is not None:
            blocks.append(earlier)
            earlier = previous_block(earlier, period, self._schedule)
        blocks.reverse()
        return blocks
