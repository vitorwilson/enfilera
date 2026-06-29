"""Telegram handler for "how's the line right now?" (/agora).

Reads the user's selected line, asks the openness service whether the
cafeteria is taking timers, and — when open — turns the estimation service's
number into the single "~N min" line. When shut it shows the closed message,
naming the closure reason when one was declared. The handler stays thin: the
open/closed decision and the estimate live in injected services; the messages
are pure functions.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from enfilera.estimate import format_estimate
from enfilera.estimate_service import EstimationService
from enfilera.lines import Line
from enfilera.messages import NO_LINE, closed_message
from enfilera.openness_service import OpennessService
from enfilera.preferences_store import LinePreferenceStore, chosen_line

COMMAND = "agora"


def estimate_message(line: Line, seconds: int) -> str:
    """The single user-facing wait line, e.g. 'Pix: ~12 min de espera.'"""
    return f"{line.label}: {format_estimate(seconds)} de espera."


class WaitEstimate:
    """Wires /agora to the openness and estimation services."""

    def __init__(
        self,
        lines: tuple[Line, ...],
        preferences: LinePreferenceStore,
        openness: OpennessService,
        estimates: EstimationService,
        clock: Callable[[], datetime],
    ) -> None:
        self._lines = lines
        self._preferences = preferences
        self._openness = openness
        self._estimates = estimates
        self._clock = clock

    def register(self, application: Application) -> None:
        """Add the /agora command handler to ``application``."""
        application.add_handler(CommandHandler(COMMAND, self.show))

    async def show(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Reply with the user's line estimate, or why the cafeteria is shut."""
        line = chosen_line(self._preferences, self._lines, update.effective_user.id)
        if line is None:
            await update.effective_message.reply_text(NO_LINE)
            return
        now = self._clock()
        status = self._openness.status(now)
        if not status.is_open:
            await update.effective_message.reply_text(closed_message(status))
            return
        seconds = self._estimates.current_estimate(now, line.id)
        if seconds is None:
            # Invariant: open ⇒ inside a period ⇒ an estimate (≥ the seed)
            # always exists. Surface a loud error (caught by ErrorReporter)
            # rather than assert, which `python -O` would strip.
            raise RuntimeError(
                f"open period yielded no estimate for line {line.id!r} at "
                f"{now.isoformat()}"
            )
        await update.effective_message.reply_text(estimate_message(line, seconds))
