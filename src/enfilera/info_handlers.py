"""Telegram handlers for the bug-report and author/credit links.

Two trivial static-reply commands whose URLs come from config so a fork points
them at its own repo and profile (``[bot].issues_url`` / ``author_url``):
``/bug`` links the issue tracker, ``/sobre`` credits the operator. Kept
separate from the data handlers because they touch no stores or services.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BUG_COMMAND = "bug"
ABOUT_COMMAND = "sobre"


def bug_message(issues_url: str) -> str:
    """Where to report a problem.

    >>> bug_message("https://example.test/issues")
    'Achou um bug? Relate aqui: https://example.test/issues'
    """
    return f"Achou um bug? Relate aqui: {issues_url}"


def about_message(author_url: str) -> str:
    """Project credit linking the operator's profile."""
    return f"Enfilera — filas do bandejão, feito por {author_url}"


class InfoLinks:
    """Wires /bug and /sobre to the config-provided URLs."""

    def __init__(self, issues_url: str, author_url: str) -> None:
        self._issues_url = issues_url
        self._author_url = author_url

    def register(self, application: Application) -> None:
        """Add the /bug and /sobre command handlers to ``application``."""
        application.add_handler(CommandHandler(BUG_COMMAND, self.bug))
        application.add_handler(CommandHandler(ABOUT_COMMAND, self.about))

    async def bug(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """``/bug`` — link the issue tracker."""
        await update.effective_message.reply_text(bug_message(self._issues_url))

    async def about(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """``/sobre`` — credit the operator."""
        await update.effective_message.reply_text(about_message(self._author_url))
