"""Per-user flood guard: a pre-handler that drops a flooding user's updates.

Runs before every feature handler (group below the default). It feeds each
update's user into the sliding-window rate limiter; once a user exceeds the
cap, it stops the update from reaching any handler (``ApplicationHandlerStop``)
so button-mashing or command spam cannot exhaust the Pi (docs/PLAN.md §3). Time
is a monotonic clock passed in, so the limiter stays deterministic and
testable.
"""

from __future__ import annotations

from collections.abc import Callable

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    ContextTypes,
    TypeHandler,
)

from enfilera.rate_limit import RateLimiter

# Negative group runs ahead of the feature handlers in the default group 0.
_FLOOD_GROUP = -1


class FloodGuard:
    """Halt updates from a user who exceeds the per-user rate limit."""

    def __init__(self, limiter: RateLimiter, clock: Callable[[], float]) -> None:
        self._limiter = limiter
        self._clock = clock

    def register(self, application: Application) -> None:
        """Install the guard ahead of every other handler."""
        application.add_handler(TypeHandler(Update, self.check), group=_FLOOD_GROUP)

    async def check(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Let the update through, or halt it when the user is flooding."""
        user = update.effective_user
        if user is None:
            return
        if not self._limiter.allow(user.id, self._clock()):
            raise ApplicationHandlerStop
