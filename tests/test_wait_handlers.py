"""Tests for the how's-the-line handler (/agora).

Wires the real stores, openness, and estimation services over the in-memory
DB with a fixed clock, and drives the async handler through the shared fakes.
2026-06-30 is a Tuesday (operating day); 2026-07-04 is a Saturday.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Coroutine
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from telegram.ext import ApplicationBuilder, CommandHandler
from telegram_fakes import FakeMessage, FakeUpdate, FakeUser

from enfilera.closures import Closure
from enfilera.closures_store import ClosureStore
from enfilera.estimate_service import EstimationService
from enfilera.estimation_config import EstimationConfig
from enfilera.halt_flag import HaltFlag
from enfilera.lines import Line
from enfilera.openness_service import OpennessService
from enfilera.preferences_store import LinePreferenceStore
from enfilera.samples_store import SampleStore
from enfilera.schedule import build_schedule
from enfilera.wait_handlers import WaitEstimate

SP = ZoneInfo("America/Sao_Paulo")
LINES = (Line("card", "Cartão"), Line("pix", "Pix"))
USER = 7
LUNCH = datetime(2026, 6, 30, 12, 15, tzinfo=SP)


def _run(coro: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coro)


def _schedule() -> object:
    return build_schedule(
        {
            "restaurant": {"timezone": "America/Sao_Paulo"},
            "schedule": {
                "operating_days": [1, 2, 3, 4, 5],
                "block_minutes": 60,
                "periods": [
                    {"id": "lunch", "start": "10:30", "end": "14:30"},
                    {"id": "dinner", "start": "17:00", "end": "20:00"},
                ],
            },
        }
    )


def _config() -> EstimationConfig:
    return EstimationConfig(
        min_samples=3, default_seed=60, clamp_min=60, clamp_max=3600, mad_k=3.0
    )


def _handler(conn: sqlite3.Connection, now: datetime = LUNCH) -> WaitEstimate:
    schedule = _schedule()
    openness = OpennessService(schedule, ClosureStore(conn), HaltFlag(conn))
    estimates = EstimationService(SampleStore(conn), schedule, _config(), 30)
    return WaitEstimate(
        LINES, LinePreferenceStore(conn), openness, estimates, lambda: now
    )


def _ask(handler: WaitEstimate) -> str:
    message = FakeMessage()
    update = FakeUpdate(effective_message=message, effective_user=FakeUser(USER))
    _run(handler.show(update, None))
    return message.replies[0][0]


def test_no_line_prompts_selection(memory_db: sqlite3.Connection) -> None:
    assert "/fila" in _ask(_handler(memory_db))


def test_stale_line_prompts_selection(memory_db: sqlite3.Connection) -> None:
    LinePreferenceStore(memory_db).set_line(USER, "ghost")
    assert "/fila" in _ask(_handler(memory_db))


def test_open_with_no_samples_shows_default_seed(memory_db: sqlite3.Connection) -> None:
    LinePreferenceStore(memory_db).set_line(USER, "card")
    text = _ask(_handler(memory_db))
    assert "Cartão" in text
    assert "~1 min" in text  # default_seed = 60s


def test_open_shows_robust_estimate(memory_db: sqlite3.Connection) -> None:
    LinePreferenceStore(memory_db).set_line(USER, "card")
    store = SampleStore(memory_db)
    for value in (600, 660, 720):  # Tuesday-noon block; median 660s = 11 min
        store.add("card", 2, time(12, 0), value, LUNCH)
    assert "~11 min" in _ask(_handler(memory_db))


def test_closed_when_halted_shows_closed_message(memory_db: sqlite3.Connection) -> None:
    LinePreferenceStore(memory_db).set_line(USER, "card")
    HaltFlag(memory_db).set(True)
    text = _ask(_handler(memory_db))
    assert "Fechado" in text
    assert "min" not in text


def test_closed_names_the_closure_reason(memory_db: sqlite3.Connection) -> None:
    LinePreferenceStore(memory_db).set_line(USER, "card")
    ClosureStore(memory_db).declare(Closure(date(2026, 6, 30), None, "feriado"))
    assert "feriado" in _ask(_handler(memory_db))


def test_register_adds_command_handler(memory_db: sqlite3.Connection) -> None:
    app = ApplicationBuilder().token("123:abc").job_queue(None).build()
    _handler(memory_db).register(app)
    assert any(isinstance(h, CommandHandler) for h in app.handlers[0])
