"""Tests for the admin authorization guard."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from telegram_fakes import FakeMessage, FakeUpdate, FakeUser

from enfilera.admin_guard import DENIED, AdminGuard

ADMINS = frozenset({7, 8})


def _run(coro: Coroutine[Any, Any, bool]) -> bool:
    return asyncio.run(coro)


def _authorize(user_id: int | None) -> tuple[bool, FakeMessage]:
    user = None if user_id is None else FakeUser(user_id)
    message = FakeMessage()
    update = FakeUpdate(effective_message=message, effective_user=user)
    allowed = _run(AdminGuard(ADMINS).authorize(update))
    return allowed, message


def test_allows_only_listed_ids() -> None:
    guard = AdminGuard(ADMINS)
    assert guard.allows(7) is True
    assert guard.allows(9) is False


def test_authorize_admit_an_admin_without_replying() -> None:
    allowed, message = _authorize(7)
    assert allowed is True
    assert message.replies == []


def test_authorize_rejects_a_stranger_with_a_refusal() -> None:
    allowed, message = _authorize(99)
    assert allowed is False
    assert message.replies[-1][0] == DENIED


def test_authorize_rejects_an_update_without_a_user() -> None:
    allowed, message = _authorize(None)
    assert allowed is False
    assert message.replies[-1][0] == DENIED
