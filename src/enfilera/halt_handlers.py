"""Operator commands for the halt flag and the live status read.

``/pausar`` and ``/retomar`` flip the dynamic halt flag — the operator's
indefinite pause that overrides hours and closures (openness.py). ``/status``
reports the current open/closed/halt state and why. All three sit behind the
admin guard and are otherwise thin: the flag write is the store's job, the
open/closed decision is the openness service's, the wording is a pure builder.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from enfilera.admin_guard import AdminGuard, admin_only
from enfilera.admin_messages import HALTED, RESUMED, admin_status
from enfilera.halt_flag import HaltFlag
from enfilera.openness_service import OpennessService

PAUSE_COMMAND = "pausar"
RESUME_COMMAND = "retomar"
STATUS_COMMAND = "status"

_logger = logging.getLogger(__name__)


class HaltControls:
    """Wires /pausar, /retomar, and /status to the halt flag and openness."""

    def __init__(
        self,
        guard: AdminGuard,
        halt: HaltFlag,
        openness: OpennessService,
        clock: Callable[[], datetime],
    ) -> None:
        self._guard = guard
        self._halt = halt
        self._openness = openness
        self._clock = clock

    def register(self, application: Application) -> None:
        """Add the /pausar, /retomar, and /status command handlers."""
        application.add_handler(CommandHandler(PAUSE_COMMAND, self.pause))
        application.add_handler(CommandHandler(RESUME_COMMAND, self.resume))
        application.add_handler(CommandHandler(STATUS_COMMAND, self.status))

    @admin_only
    async def pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """``/pausar`` — halt the bot until an admin resumes it."""
        self._halt.set(True)
        _logger.info("bot halted", extra={"user_id": update.effective_user.id})
        await update.effective_message.reply_text(HALTED)

    @admin_only
    async def resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """``/retomar`` — lift the halt and return to normal operation."""
        self._halt.set(False)
        _logger.info("bot resumed", extra={"user_id": update.effective_user.id})
        await update.effective_message.reply_text(RESUMED)

    @admin_only
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """``/status`` — report the current open/closed/halt state and why."""
        await update.effective_message.reply_text(
            admin_status(self._openness.status(self._clock()))
        )
