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
from enfilera.lines import Line, find_line
from enfilera.openness import ClosedStatus
from enfilera.openness_service import OpennessService
from enfilera.preferences_store import LinePreferenceStore

COMMAND = "agora"

_NO_LINE = "Escolha sua fila primeiro com /fila."
_CLOSED = "Fechado agora. Volte no horário de funcionamento."


def estimate_message(line: Line, seconds: int) -> str:
    """The single user-facing wait line, e.g. 'Pix: ~12 min de espera.'"""
    return f"{line.label}: {format_estimate(seconds)} de espera."


def closed_message(status: ClosedStatus) -> str:
    """Closed notice, naming the closure reason when one was declared."""
    if status.detail:
        return f"Fechado agora: {status.detail}."
    return _CLOSED


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
        line = self._chosen_line(update.effective_user.id)
        if line is None:
            await update.effective_message.reply_text(_NO_LINE)
            return
        now = self._clock()
        status = self._openness.status(now)
        if not status.is_open:
            await update.effective_message.reply_text(closed_message(status))
            return
        seconds = self._estimates.current_estimate(now, line.id)
        assert seconds is not None  # open ⇒ inside a period ⇒ estimate exists
        await update.effective_message.reply_text(estimate_message(line, seconds))

    def _chosen_line(self, user_id: int) -> Line | None:
        line_id = self._preferences.get_line(user_id)
        return None if line_id is None else find_line(self._lines, line_id)
