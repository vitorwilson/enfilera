"""Tests for the bug-report and author/credit link handlers."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from telegram.ext import ApplicationBuilder, CommandHandler
from telegram_fakes import FakeMessage, FakeUpdate, FakeUser

from enfilera.info_handlers import InfoLinks, about_message, bug_message

ISSUES = "https://github.com/someone/enfilera/issues"
AUTHOR = "https://github.com/someone"


def _run(coro: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coro)


def _links() -> InfoLinks:
    return InfoLinks(ISSUES, AUTHOR)


def _ask(method: str) -> str:
    update = FakeUpdate(effective_message=FakeMessage(), effective_user=FakeUser(7))
    _run(getattr(_links(), method)(update, None))
    return update.effective_message.replies[-1][0]


def test_bug_message_includes_the_issues_url() -> None:
    assert ISSUES in bug_message(ISSUES)


def test_about_message_includes_the_author_url() -> None:
    assert AUTHOR in about_message(AUTHOR)


def test_bug_handler_replies_with_issues_link() -> None:
    assert ISSUES in _ask("bug")


def test_about_handler_replies_with_author_link() -> None:
    assert AUTHOR in _ask("about")


def test_register_adds_both_command_handlers() -> None:
    app = ApplicationBuilder().token("123:abc").job_queue(None).build()
    _links().register(app)
    assert sum(isinstance(h, CommandHandler) for h in app.handlers[0]) == 2
