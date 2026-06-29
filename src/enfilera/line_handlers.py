"""Telegram handler for picking and changing your line.

The user runs ``/fila`` to get an inline keyboard of the cafeteria's lines
(from config); tapping one persists the choice via the line-preference store
and the bot confirms. The selection is changeable anytime by running ``/fila``
again. The handler stays thin: keyboard building and callback encoding are
pure functions; the async methods only glue Telegram to the store.
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from enfilera.lines import Line, find_line
from enfilera.preferences_store import LinePreferenceStore

COMMAND = "fila"
# Callback data is namespaced so a single CallbackQueryHandler owns line taps
# and never collides with other inline keyboards (admin, etc.).
CALLBACK_PATTERN = r"^line:"
_CALLBACK_PREFIX = "line:"

_PROMPT = "Qual fila você quer acompanhar?"
_UNKNOWN_LINE = "Essa fila não existe mais. Use /fila para escolher de novo."

_logger = logging.getLogger(__name__)


def encode_choice(line_id: str) -> str:
    """Callback data for choosing ``line_id``.

    >>> encode_choice("pix")
    'line:pix'
    """
    return f"{_CALLBACK_PREFIX}{line_id}"


def decode_choice(data: str) -> str | None:
    """The line id inside callback ``data``, or ``None`` if it isn't a line tap.

    >>> decode_choice("line:pix")
    'pix'
    >>> decode_choice("admin:halt") is None
    True
    """
    if not data.startswith(_CALLBACK_PREFIX):
        return None
    return data[len(_CALLBACK_PREFIX) :]


def line_keyboard(lines: tuple[Line, ...]) -> InlineKeyboardMarkup:
    """One button per line: the label is shown, the id rides the callback."""
    rows = [
        [InlineKeyboardButton(line.label, callback_data=encode_choice(line.id))]
        for line in lines
    ]
    return InlineKeyboardMarkup(rows)


def confirmation(line: Line) -> str:
    """User-facing message shown after a successful pick.

    >>> confirmation(Line("pix", "Pix"))
    'Pronto! Sua fila agora é: Pix.'
    """
    return f"Pronto! Sua fila agora é: {line.label}."


class LineSelection:
    """Wires the ``/fila`` command and its line-tap callbacks to the store."""

    def __init__(
        self, lines: tuple[Line, ...], preferences: LinePreferenceStore
    ) -> None:
        self._lines = lines
        self._preferences = preferences

    def register(self, application: Application) -> None:
        """Add the command and callback handlers to ``application``."""
        application.add_handler(CommandHandler(COMMAND, self.show_menu))
        application.add_handler(
            CallbackQueryHandler(self.on_choice, pattern=CALLBACK_PATTERN)
        )

    async def show_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """``/fila`` — present the line picker."""
        await update.effective_message.reply_text(
            _PROMPT, reply_markup=line_keyboard(self._lines)
        )

    async def on_choice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Persist the tapped line and confirm it; reject an unknown id."""
        query = update.callback_query
        await query.answer()
        line_id = decode_choice(query.data)
        line = None if line_id is None else find_line(self._lines, line_id)
        if line is None:
            await query.edit_message_text(_UNKNOWN_LINE)
            return
        user_id = update.effective_user.id
        self._preferences.set_line(user_id, line.id)
        _logger.info("line selected", extra={"user_id": user_id, "line_id": line.id})
        await query.edit_message_text(confirmation(line))
