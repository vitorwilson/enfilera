"""Persist a finished transit as a sample and burn the one-per-period flag.

A measured wait belongs to the block its *queue-join* (start) falls in — that
is the moment whose queue conditions the sample describes — so both the sample
bucket (weekday, block) and the period the user "spends" are derived from the
start timestamp, in server time. Bundles the sample store, the submission
store, and the schedule so the timer handler stays a thin orchestrator.
"""

from __future__ import annotations

from datetime import datetime

from enfilera.openness import current_period
from enfilera.samples_store import SampleStore
from enfilera.schedule import Schedule, block_for
from enfilera.submissions_store import SubmissionStore


class SubmissionRecorder:
    """Record a validated transit and mark its period as used."""

    def __init__(
        self,
        samples: SampleStore,
        submissions: SubmissionStore,
        schedule: Schedule,
    ) -> None:
        self._samples = samples
        self._submissions = submissions
        self._schedule = schedule

    def already_submitted(self, user_id: int, when: datetime) -> bool:
        """Whether ``user_id`` already submitted in the period ``when`` is in."""
        period = current_period(when, self._schedule)
        if period is None:
            return False
        return self._submissions.has_submitted(user_id, period.date, period.period_id)

    def record(
        self, user_id: int, line_id: str, start: datetime, elapsed_seconds: int
    ) -> None:
        """Store the sample in the start block and mark the start period used."""
        local = start.astimezone(self._schedule.timezone)
        block = block_for(local.time(), self._schedule)
        self._samples.add(
            line_id, local.isoweekday(), block.start, elapsed_seconds, start
        )
        period = current_period(start, self._schedule)
        if period is None:
            raise ValueError(f"start {start!r} is outside every operating period")
        self._submissions.mark(user_id, period.date, period.period_id)
