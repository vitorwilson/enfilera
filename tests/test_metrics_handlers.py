"""Tests for the /usuarios user-metrics admin handler.

Wires the real metrics store over the in-memory DB with a fixed clock and
config lines, then drives the async handler through the shared fakes.
Submissions are seeded through the real SubmissionStore. The clock is
2026-06-30 12:15 in São Paulo, so "today" is 2026-06-30 and the 30-day window
opens at 2026-06-01; the guard is exercised too.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Coroutine
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from schedules import make_schedule as _schedule
from telegram.ext import ApplicationBuilder, CommandHandler
from telegram_fakes import FakeContext, FakeMessage, FakeUpdate, FakeUser

from enfilera.admin_guard import DENIED, AdminGuard
from enfilera.lines import Line
from enfilera.metrics_handlers import MetricsControls
from enfilera.submissions_store import SubmissionStore
from enfilera.user_metrics_store import UserMetricsStore

SP = ZoneInfo("America/Sao_Paulo")
ADMIN = 7
STRANGER = 99
NOW = datetime(2026, 6, 30, 12, 15, tzinfo=SP)
TODAY = date(2026, 6, 30)
IN_WINDOW = date(2026, 6, 10)
BEFORE_WINDOW = date(2026, 5, 1)
LINES = (Line("card", "Cartão"), Line("pix", "Pix"))


def _run(coro: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coro)


def _controls(conn: sqlite3.Connection) -> MetricsControls:
    return MetricsControls(
        AdminGuard(frozenset({ADMIN})),
        UserMetricsStore(conn),
        LINES,
        _schedule(),
        lambda: NOW,
    )


def _mark(conn: sqlite3.Connection, user_id: int, when: date, line: str) -> None:
    SubmissionStore(conn).mark(user_id, when, "lunch", line)


def _invoke(controls: MetricsControls, user_id: int) -> str:
    message = FakeMessage()
    update = FakeUpdate(effective_message=message, effective_user=FakeUser(user_id))
    _run(controls.report(update, FakeContext()))
    return message.replies[-1][0]


def test_reports_today_and_window_totals(memory_db: sqlite3.Connection) -> None:
    _mark(memory_db, 1, TODAY, "card")
    _mark(memory_db, 2, TODAY, "pix")
    _mark(memory_db, 3, IN_WINDOW, "card")
    _mark(memory_db, 4, BEFORE_WINDOW, "pix")  # outside the 30-day window
    reply = _invoke(_controls(memory_db), ADMIN)
    assert "• Hoje: 2" in reply
    assert "• Últimos 30 dias: 3" in reply


def test_breaks_down_by_line_in_config_order(memory_db: sqlite3.Connection) -> None:
    _mark(memory_db, 1, TODAY, "pix")
    _mark(memory_db, 2, IN_WINDOW, "card")
    _mark(memory_db, 3, TODAY, "card")
    reply = _invoke(_controls(memory_db), ADMIN)
    assert "• Cartão: 2" in reply
    assert "• Pix: 1" in reply
    assert reply.index("Cartão") < reply.index("Pix")  # config order preserved


def test_configured_line_with_no_users_shows_zero(
    memory_db: sqlite3.Connection,
) -> None:
    _mark(memory_db, 1, TODAY, "card")
    reply = _invoke(_controls(memory_db), ADMIN)
    assert "• Pix: 0" in reply


def test_unknown_line_folds_into_desconhecida(memory_db: sqlite3.Connection) -> None:
    memory_db.execute(
        "INSERT INTO submissions (user_id, period_date, period_id) VALUES (?, ?, ?)",
        (9, TODAY.isoformat(), "lunch"),
    )
    memory_db.commit()
    reply = _invoke(_controls(memory_db), ADMIN)
    assert "• desconhecida: 1" in reply
    assert "• Últimos 30 dias: 1" in reply


def test_non_admin_is_denied(memory_db: sqlite3.Connection) -> None:
    _mark(memory_db, 1, TODAY, "card")
    assert _invoke(_controls(memory_db), STRANGER) == DENIED


def test_register_adds_one_command_handler(memory_db: sqlite3.Connection) -> None:
    app = ApplicationBuilder().token("123:abc").job_queue(None).build()
    _controls(memory_db).register(app)
    assert sum(isinstance(h, CommandHandler) for h in app.handlers[0]) == 1
