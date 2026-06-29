"""Tests for the halt/resume/status admin handlers (/pausar, /retomar, /status).

Wires the real halt flag and openness service over the in-memory DB with a
fixed clock, and drives the async handlers through the shared fakes. The guard
is exercised here too: a non-admin must change nothing. 2026-06-30 is a Tuesday
(operating day, lunch at 12:15); 2026-07-04 is a Saturday.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Coroutine
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from schedules import make_schedule as _schedule
from telegram.ext import ApplicationBuilder, CommandHandler
from telegram_fakes import FakeContext, FakeMessage, FakeUpdate, FakeUser

from enfilera.admin_guard import DENIED, AdminGuard
from enfilera.closures_store import ClosureStore
from enfilera.halt_flag import HaltFlag
from enfilera.halt_handlers import HaltControls
from enfilera.openness_service import OpennessService

SP = ZoneInfo("America/Sao_Paulo")
ADMIN = 7
STRANGER = 99
LUNCH = datetime(2026, 6, 30, 12, 15, tzinfo=SP)
WEEKEND = datetime(2026, 7, 4, 12, 15, tzinfo=SP)


def _run(coro: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coro)


def _controls(conn: sqlite3.Connection, now: datetime = LUNCH) -> HaltControls:
    schedule = _schedule()
    openness = OpennessService(schedule, ClosureStore(conn), HaltFlag(conn))
    return HaltControls(
        AdminGuard(frozenset({ADMIN})), HaltFlag(conn), openness, lambda: now
    )


def _invoke(controls: HaltControls, method: str, user_id: int) -> str:
    message = FakeMessage()
    update = FakeUpdate(effective_message=message, effective_user=FakeUser(user_id))
    _run(getattr(controls, method)(update, FakeContext()))
    return message.replies[-1][0]


# --- halt / resume -------------------------------------------------------


def test_pause_sets_the_halt_flag(memory_db: sqlite3.Connection) -> None:
    reply = _invoke(_controls(memory_db), "pause", ADMIN)
    assert HaltFlag(memory_db).is_enabled() is True
    assert "pausado" in reply.lower()


def test_resume_clears_the_halt_flag(memory_db: sqlite3.Connection) -> None:
    HaltFlag(memory_db).set(True)
    reply = _invoke(_controls(memory_db), "resume", ADMIN)
    assert HaltFlag(memory_db).is_enabled() is False
    assert "retomado" in reply.lower()


def test_non_admin_pause_is_denied_and_changes_nothing(
    memory_db: sqlite3.Connection,
) -> None:
    reply = _invoke(_controls(memory_db), "pause", STRANGER)
    assert reply == DENIED
    assert HaltFlag(memory_db).is_enabled() is False


# --- status --------------------------------------------------------------


def test_status_reports_open_with_period(memory_db: sqlite3.Connection) -> None:
    reply = _invoke(_controls(memory_db, LUNCH), "status", ADMIN)
    assert "Aberto" in reply
    assert "lunch" in reply


def test_status_reports_halt(memory_db: sqlite3.Connection) -> None:
    HaltFlag(memory_db).set(True)
    reply = _invoke(_controls(memory_db, LUNCH), "status", ADMIN)
    assert "Pausado" in reply


def test_status_reports_non_operating_day(memory_db: sqlite3.Connection) -> None:
    reply = _invoke(_controls(memory_db, WEEKEND), "status", ADMIN)
    assert "Fechado" in reply


def test_status_is_admin_only(memory_db: sqlite3.Connection) -> None:
    assert _invoke(_controls(memory_db), "status", STRANGER) == DENIED


# --- registration --------------------------------------------------------


def test_register_adds_three_command_handlers(memory_db: sqlite3.Connection) -> None:
    app = ApplicationBuilder().token("123:abc").job_queue(None).build()
    _controls(memory_db).register(app)
    assert sum(isinstance(h, CommandHandler) for h in app.handlers[0]) == 3
