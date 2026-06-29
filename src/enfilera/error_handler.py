"""Catch-all for unhandled errors raised inside a handler.

Without this, an exception in any handler is swallowed by PTB's default — the
user gets silence and the only trace is PTB's own logger. This registers one
error handler that logs the failure as a structured record and tells the user,
in plain text, that something broke, so a bug is visible to both the operator
(in the logs) and the user (instead of a dead non-response).
"""

from __future__ import annotations

import logging

from telegram.ext import Application, ContextTypes

_logger = logging.getLogger(__name__)

_USER_MESSAGE = "Algo deu errado. Tente de novo em instantes."


class ErrorReporter:
    """Logs any unhandled handler error and notifies the user it failed."""

    def register(self, application: Application) -> None:
        """Install the catch-all error handler on ``application``."""
        application.add_error_handler(self.report)

    async def report(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log the error and, when possible, tell the user it went wrong."""
        _logger.error("unhandled handler error", exc_info=context.error)
        message = getattr(update, "effective_message", None)
        if message is None:
            return
        try:
            await message.reply_text(_USER_MESSAGE)
        except Exception:  # noqa: BLE001 — reporting must never raise and mask
            # the original error; a failed notify is itself just logged.
            _logger.exception("failed to notify the user about an error")
