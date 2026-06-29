"""Tests for the catch-all error handler."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

import pytest
from telegram.ext import ApplicationBuilder
from telegram_fakes import FakeContext, FakeMessage, FakeUpdate

from enfilera.error_handler import _USER_MESSAGE, ErrorReporter


def _run(coro: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coro)


class RaisingMessage:
    """A message whose reply_text fails, to prove reporting never re-raises."""

    async def reply_text(self, text: str, reply_markup: object = None) -> None:
        raise RuntimeError("telegram is down")


def test_reports_to_the_user_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    message = FakeMessage()
    update = FakeUpdate(effective_message=message)
    context = FakeContext(error=ValueError("boom"))
    with caplog.at_level(logging.ERROR):
        _run(ErrorReporter().report(update, context))
    assert message.replies[-1][0] == _USER_MESSAGE
    assert "unhandled handler error" in caplog.text


def test_no_message_means_no_reply_and_no_crash() -> None:
    # An error with no associated update (update is None) must not raise.
    _run(ErrorReporter().report(None, FakeContext(error=ValueError("boom"))))


def test_a_failing_reply_is_swallowed() -> None:
    update = FakeUpdate(effective_message=RaisingMessage())
    # Must not propagate the reply failure (which would mask the original error).
    _run(ErrorReporter().report(update, FakeContext(error=ValueError("boom"))))


def test_register_adds_an_error_handler() -> None:
    app = ApplicationBuilder().token("123:abc").job_queue(None).build()
    ErrorReporter().register(app)
    assert app.error_handlers
