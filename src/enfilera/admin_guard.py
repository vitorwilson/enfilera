"""Authorization for the operator commands: allowlisted Telegram IDs only.

Every admin handler funnels through one ``AdminGuard`` so the membership check
and the denial reply live in a single place (Feature 5 / docs/PLAN.md §4). The
allowlist is the static ``[bot].admin_ids`` from config; a user not on it gets
a short refusal and the handler returns without touching any dynamic state.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Protocol

from telegram import Update
from telegram.ext import ContextTypes

DENIED = "Comando restrito ao operador."


class AdminGuard:
    """Gate operator commands behind the configured Telegram-ID allowlist."""

    def __init__(self, admin_ids: frozenset[int]) -> None:
        self._admin_ids = admin_ids

    def allows(self, user_id: int) -> bool:
        """Whether ``user_id`` is on the admin allowlist.

        >>> AdminGuard(frozenset({7})).allows(7)
        True
        >>> AdminGuard(frozenset({7})).allows(8)
        False
        """
        return user_id in self._admin_ids

    async def authorize(self, update: Update) -> bool:
        """True if the update's user may proceed; else reply a refusal.

        The handler calls this first and returns early on ``False``, so an
        unauthorized update never reaches the dynamic-state mutation below it.
        """
        user = update.effective_user
        if user is not None and self.allows(user.id):
            return True
        await update.effective_message.reply_text(DENIED)
        return False


class _Guarded(Protocol):
    """A handler that holds an :class:`AdminGuard` to authorize through."""

    _guard: AdminGuard


_AdminHandler = Callable[[_Guarded, Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


def admin_only(method: _AdminHandler) -> _AdminHandler:
    """Run a handler method only for an authorized admin, else reply the refusal.

    Keeps the allowlist check in one place across every operator command: the
    decorated method body never runs for a non-admin update.
    """

    @functools.wraps(method)
    async def guarded(
        self: _Guarded, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._guard.authorize(update):
            return
        await method(self, update, context)

    return guarded
