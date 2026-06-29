"""Tests for the live-status resolver that feeds status_at from the stores.

Uses the real in-memory store fixture and a real schedule; ``now`` is passed
in (timezone-aware) so the resolver is deterministic. 2026-06-30 is a Tuesday
(operating day); 2026-07-04 is a Saturday.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from zoneinfo import ZoneInfo

from schedules import make_schedule as _schedule

from enfilera.closures import Closure
from enfilera.closures_store import ClosureStore
from enfilera.halt_flag import HaltFlag
from enfilera.openness import ClosedReason, ClosedStatus, OpenStatus
from enfilera.openness_service import OpennessService

SP = ZoneInfo("America/Sao_Paulo")


def _service(conn: sqlite3.Connection) -> OpennessService:
    return OpennessService(_schedule(), ClosureStore(conn), HaltFlag(conn))


def _sp(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SP)


def test_open_during_lunch(memory_db: sqlite3.Connection) -> None:
    status = _service(memory_db).status(_sp(2026, 6, 30, 12, 15))
    assert isinstance(status, OpenStatus)
    assert status.period_id == "lunch"


def test_closed_when_halted(memory_db: sqlite3.Connection) -> None:
    HaltFlag(memory_db).set(True)
    status = _service(memory_db).status(_sp(2026, 6, 30, 12, 15))
    assert status == ClosedStatus(ClosedReason.HALTED)


def test_closed_by_whole_day_closure_carries_reason(
    memory_db: sqlite3.Connection,
) -> None:
    ClosureStore(memory_db).declare(Closure(date(2026, 6, 30), None, "feriado"))
    status = _service(memory_db).status(_sp(2026, 6, 30, 12, 15))
    assert isinstance(status, ClosedStatus)
    assert status.reason == ClosedReason.CLOSURE
    assert status.detail == "feriado"


def test_closed_outside_periods(memory_db: sqlite3.Connection) -> None:
    status = _service(memory_db).status(_sp(2026, 6, 30, 15, 0))
    assert status == ClosedStatus(ClosedReason.OUTSIDE_PERIODS)


def test_closed_on_non_operating_day(memory_db: sqlite3.Connection) -> None:
    status = _service(memory_db).status(_sp(2026, 7, 4, 12, 0))
    assert status == ClosedStatus(ClosedReason.NON_OPERATING_DAY)


def test_period_closure_shuts_only_that_period(memory_db: sqlite3.Connection) -> None:
    ClosureStore(memory_db).declare(Closure(date(2026, 6, 30), "dinner", "sem janta"))
    service = _service(memory_db)
    assert isinstance(service.status(_sp(2026, 6, 30, 12, 15)), OpenStatus)
    shut = service.status(_sp(2026, 6, 30, 18, 15))
    assert isinstance(shut, ClosedStatus)
    assert shut.reason == ClosedReason.CLOSURE
