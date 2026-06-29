"""Tests for the line-selection Telegram handler.

The pure helpers (callback encoding, keyboard, confirmation text) are tested
directly. The async glue is driven with ``asyncio.run`` over named fake
Telegram objects, and persists through the real in-memory store fixture.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Coroutine
from typing import Any

from telegram import InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

from enfilera.line_handlers import (
    LineSelection,
    confirmation,
    decode_choice,
    encode_choice,
    line_keyboard,
)
from enfilera.lines import Line
from enfilera.preferences_store import LinePreferenceStore

LINES = (Line("card", "Cartão"), Line("pix", "Pix"))
USER = 7


def _run(coro: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coro)


class FakeMessage:
    """Records reply_text calls instead of sending to Telegram."""

    def __init__(self) -> None:
        self.replies: list[tuple[str, object]] = []

    async def reply_text(self, text: str, reply_markup: object = None) -> None:
        self.replies.append((text, reply_markup))


class FakeCallbackQuery:
    """A tapped inline button: carries data, records answer/edit calls."""

    def __init__(self, data: str) -> None:
        self.data = data
        self.answered = False
        self.edits: list[str] = []

    async def answer(self) -> None:
        self.answered = True

    async def edit_message_text(self, text: str) -> None:
        self.edits.append(text)


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class FakeUpdate:
    """Stand-in exposing only the attributes the handler reads."""

    def __init__(
        self,
        *,
        effective_message: FakeMessage | None = None,
        callback_query: FakeCallbackQuery | None = None,
        effective_user: FakeUser | None = None,
    ) -> None:
        self.effective_message = effective_message
        self.callback_query = callback_query
        self.effective_user = effective_user


def _selection(conn: sqlite3.Connection) -> LineSelection:
    return LineSelection(LINES, LinePreferenceStore(conn))


# --- pure helpers ----------------------------------------------------------


def test_encode_decode_roundtrip() -> None:
    assert decode_choice(encode_choice("pix")) == "pix"


def test_decode_rejects_foreign_callback_data() -> None:
    assert decode_choice("admin:halt") is None


def test_line_keyboard_has_one_button_per_line() -> None:
    markup = line_keyboard(LINES)
    assert isinstance(markup, InlineKeyboardMarkup)
    buttons = [b for row in markup.inline_keyboard for b in row]
    assert [b.text for b in buttons] == ["Cartão", "Pix"]
    assert [b.callback_data for b in buttons] == ["line:card", "line:pix"]


def test_confirmation_names_the_line() -> None:
    assert "Pix" in confirmation(Line("pix", "Pix"))


# --- async glue ------------------------------------------------------------


def test_show_menu_sends_prompt_and_keyboard(memory_db: sqlite3.Connection) -> None:
    message = FakeMessage()
    update = FakeUpdate(effective_message=message)
    _run(_selection(memory_db).show_menu(update, None))
    text, markup = message.replies[0]
    assert text and isinstance(markup, InlineKeyboardMarkup)


def test_on_choice_persists_and_confirms(memory_db: sqlite3.Connection) -> None:
    query = FakeCallbackQuery(encode_choice("pix"))
    update = FakeUpdate(callback_query=query, effective_user=FakeUser(USER))
    _run(_selection(memory_db).on_choice(update, None))
    assert LinePreferenceStore(memory_db).get_line(USER) == "pix"
    assert query.answered is True
    assert "Pix" in query.edits[0]


def test_on_choice_unknown_line_stores_nothing(memory_db: sqlite3.Connection) -> None:
    query = FakeCallbackQuery(encode_choice("ghost"))
    update = FakeUpdate(callback_query=query, effective_user=FakeUser(USER))
    _run(_selection(memory_db).on_choice(update, None))
    assert LinePreferenceStore(memory_db).get_line(USER) is None
    assert query.edits  # the user is told the line is unknown


def test_changing_line_replaces_previous(memory_db: sqlite3.Connection) -> None:
    selection = _selection(memory_db)
    for line_id in ("card", "pix"):
        query = FakeCallbackQuery(encode_choice(line_id))
        update = FakeUpdate(callback_query=query, effective_user=FakeUser(USER))
        _run(selection.on_choice(update, None))
    assert LinePreferenceStore(memory_db).get_line(USER) == "pix"


def test_register_adds_command_and_callback_handlers(
    memory_db: sqlite3.Connection,
) -> None:
    app = ApplicationBuilder().token("123:abc").job_queue(None).build()
    _selection(memory_db).register(app)
    registered = app.handlers[0]
    assert any(isinstance(h, CommandHandler) for h in registered)
    assert any(isinstance(h, CallbackQueryHandler) for h in registered)
