"""Tests for the per-user flood guard pre-handler."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

import pytest
from telegram.ext import ApplicationBuilder, ApplicationHandlerStop, TypeHandler
from telegram_fakes import FakeUpdate, FakeUser

from enfilera.flood_guard import FloodGuard
from enfilera.rate_limit import RateLimiter


class Clock:
    """A monotonic test clock advanced by the test."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _run(coro: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coro)


def _guard(clock: Clock, max_events: int = 2, window: float = 10.0) -> FloodGuard:
    return FloodGuard(RateLimiter(max_events, window), clock)


def _update(user_id: int = 7) -> FakeUpdate:
    return FakeUpdate(effective_user=FakeUser(user_id))


def test_allows_up_to_the_limit() -> None:
    guard = _guard(Clock())
    _run(guard.check(_update(), None))
    _run(guard.check(_update(), None))  # two within the cap: no raise


def test_blocks_beyond_the_limit() -> None:
    guard = _guard(Clock())
    _run(guard.check(_update(), None))
    _run(guard.check(_update(), None))
    with pytest.raises(ApplicationHandlerStop):
        _run(guard.check(_update(), None))


def test_user_is_freed_after_the_window() -> None:
    clock = Clock()
    guard = _guard(clock)
    _run(guard.check(_update(), None))
    _run(guard.check(_update(), None))
    clock.now = 11.0  # the earlier events have aged out
    _run(guard.check(_update(), None))


def test_users_are_independent() -> None:
    guard = _guard(Clock())
    _run(guard.check(_update(1), None))
    _run(guard.check(_update(1), None))
    _run(guard.check(_update(2), None))  # a different user is unaffected


def test_updates_without_a_user_are_ignored() -> None:
    guard = _guard(Clock())
    for _ in range(5):  # no effective_user: never consumes budget, never blocks
        _run(guard.check(FakeUpdate(), None))


def test_register_installs_guard_before_other_handlers() -> None:
    app = ApplicationBuilder().token("123:abc").job_queue(None).build()
    _guard(Clock()).register(app)
    assert any(isinstance(h, TypeHandler) for h in app.handlers[-1])
