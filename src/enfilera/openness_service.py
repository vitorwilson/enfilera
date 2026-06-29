"""Resolve the cafeteria's live open/closed status from dynamic state.

``openness.status_at`` is pure: it takes the schedule, the day's closures, and
the halt flag as arguments. This service supplies the dynamic two from the live
stores, so a handler asks one question — "open right now?" — without each one
wiring the closure store and halt flag itself. ``now`` is passed in (the caller
owns the server clock), keeping the same instant for the openness check and the
estimate that follows it. Shared by the how's-the-line read, the timer gate,
and the admin status command.
"""

from __future__ import annotations

from datetime import datetime

from enfilera.closures_store import ClosureStore
from enfilera.halt_flag import HaltFlag
from enfilera.openness import Status, status_at
from enfilera.schedule import Schedule


class OpennessService:
    """Answer "is the cafeteria open right now?" from the live stores."""

    def __init__(
        self, schedule: Schedule, closures: ClosureStore, halt: HaltFlag
    ) -> None:
        self._schedule = schedule
        self._closures = closures
        self._halt = halt

    def status(self, now: datetime) -> Status:
        """The live status at ``now`` (timezone-aware server time)."""
        local_date = now.astimezone(self._schedule.timezone).date()
        return status_at(
            now,
            self._schedule,
            self._closures.active_on(local_date),
            self._halt.is_enabled(),
        )
