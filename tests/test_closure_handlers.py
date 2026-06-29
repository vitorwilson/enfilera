"""Tests for the closure admin handlers (/fechar, /fechamentos, /reabrir).

Wires the real closure store over the in-memory DB with a fixed clock and
drives the async handlers through the shared fakes, passing command args via
the fake context. Covers declare (day / period / range), list, revoke (the
first-class case and the wrong-target miss), bad-argument feedback, and the
guard. The clock is fixed at 2026-06-29 (a Monday) so "hoje" is deterministic.
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
from enfilera.closure_handlers import ClosureControls
from enfilera.closures import Closure
from enfilera.closures_store import ClosureStore

SP = ZoneInfo("America/Sao_Paulo")
ADMIN = 7
STRANGER = 99
NOW = datetime(2026, 6, 29, 9, 0, tzinfo=SP)
TODAY = date(2026, 6, 29)


def _run(coro: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coro)


def _controls(conn: sqlite3.Connection) -> ClosureControls:
    return ClosureControls(
        AdminGuard(frozenset({ADMIN})), ClosureStore(conn), _schedule(), lambda: NOW
    )


def _invoke(
    controls: ClosureControls, method: str, args: list[str], user_id: int = ADMIN
) -> str:
    message = FakeMessage()
    update = FakeUpdate(effective_message=message, effective_user=FakeUser(user_id))
    _run(getattr(controls, method)(update, FakeContext(args)))
    return message.replies[-1][0]


# --- declare -------------------------------------------------------------


def test_declare_today_whole_day(memory_db: sqlite3.Connection) -> None:
    reply = _invoke(_controls(memory_db), "declare", ["hoje", "feriado"])
    assert ClosureStore(memory_db).active_on(TODAY) == [Closure(TODAY, None, "feriado")]
    assert "Fechamento declarado" in reply


def test_declare_single_period(memory_db: sqlite3.Connection) -> None:
    _invoke(_controls(memory_db), "declare", ["2026-07-01", "lunch", "sem", "almoço"])
    assert ClosureStore(memory_db).active_on(date(2026, 7, 1)) == [
        Closure(date(2026, 7, 1), "lunch", "sem almoço")
    ]


def test_declare_range_inserts_one_row_per_day(memory_db: sqlite3.Connection) -> None:
    reply = _invoke(
        _controls(memory_db), "declare", ["2026-07-01..2026-07-03", "recesso"]
    )
    store = ClosureStore(memory_db)
    assert len(store.upcoming(date(2026, 7, 1))) == 3
    assert "3 dias" in reply


def test_declare_rejects_bad_date(memory_db: sqlite3.Connection) -> None:
    reply = _invoke(_controls(memory_db), "declare", ["amanhã"])
    assert "data inválida" in reply
    assert ClosureStore(memory_db).upcoming(date(2026, 1, 1)) == []


def test_declare_empty_args_shows_usage(memory_db: sqlite3.Connection) -> None:
    assert "uso: /fechar" in _invoke(_controls(memory_db), "declare", [])


def test_declare_is_admin_only(memory_db: sqlite3.Connection) -> None:
    reply = _invoke(_controls(memory_db), "declare", ["hoje"], user_id=STRANGER)
    assert reply == DENIED
    assert ClosureStore(memory_db).active_on(TODAY) == []


# --- list ----------------------------------------------------------------


def test_list_empty_says_none(memory_db: sqlite3.Connection) -> None:
    assert "Nenhum fechamento" in _invoke(_controls(memory_db), "list_upcoming", [])


def test_list_shows_upcoming_from_today(memory_db: sqlite3.Connection) -> None:
    store = ClosureStore(memory_db)
    store.declare(Closure(date(2026, 7, 2), None, "feriado"))
    store.declare(Closure(date(2026, 1, 1), None, "passado"))  # before today
    reply = _invoke(_controls(memory_db), "list_upcoming", [])
    assert "2026-07-02" in reply
    assert "passado" not in reply


# --- revoke --------------------------------------------------------------


def test_revoke_removes_the_closure(memory_db: sqlite3.Connection) -> None:
    store = ClosureStore(memory_db)
    store.declare(Closure(date(2026, 7, 1), None, "feriado"))
    reply = _invoke(_controls(memory_db), "revoke", ["2026-07-01"])
    assert store.active_on(date(2026, 7, 1)) == []
    assert "removido" in reply


def test_revoke_missing_reports_nothing_found(memory_db: sqlite3.Connection) -> None:
    reply = _invoke(_controls(memory_db), "revoke", ["2026-07-01"])
    assert "Nenhum fechamento encontrado" in reply


def test_revoke_period_leaves_whole_day(memory_db: sqlite3.Connection) -> None:
    store = ClosureStore(memory_db)
    store.declare(Closure(date(2026, 7, 1), None, "all"))
    store.declare(Closure(date(2026, 7, 1), "lunch", None))
    _invoke(_controls(memory_db), "revoke", ["2026-07-01", "lunch"])
    assert store.active_on(date(2026, 7, 1)) == [Closure(date(2026, 7, 1), None, "all")]


def test_revoke_rejects_unknown_period(memory_db: sqlite3.Connection) -> None:
    assert "período desconhecido" in _invoke(
        _controls(memory_db), "revoke", ["2026-07-01", "brunch"]
    )


def test_revoke_is_admin_only(memory_db: sqlite3.Connection) -> None:
    store = ClosureStore(memory_db)
    store.declare(Closure(date(2026, 7, 1), None, "feriado"))
    reply = _invoke(_controls(memory_db), "revoke", ["2026-07-01"], user_id=STRANGER)
    assert reply == DENIED
    assert len(store.active_on(date(2026, 7, 1))) == 1


# --- registration --------------------------------------------------------


def test_register_adds_three_command_handlers(memory_db: sqlite3.Connection) -> None:
    app = ApplicationBuilder().token("123:abc").job_queue(None).build()
    _controls(memory_db).register(app)
    assert sum(isinstance(h, CommandHandler) for h in app.handlers[0]) == 3
