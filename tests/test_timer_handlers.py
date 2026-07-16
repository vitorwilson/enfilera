"""Tests for the register-time timer flow (/registrar → location → /parar).

Drives the full sequence over a shared fake context with an advanceable clock,
against the real stores. 2026-06-30 is a Tuesday; lunch is 10:30-14:30. The
geofence centre matches the example config; FAR is several km away.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Coroutine
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from schedules import make_schedule as _schedule
from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
)
from telegram_fakes import (
    FakeCallbackQuery,
    FakeContext,
    FakeLocation,
    FakeMessage,
    FakeUpdate,
    FakeUser,
)

from enfilera.closures_store import ClosureStore
from enfilera.estimation_config import EstimationConfig
from enfilera.geofence import Geofence
from enfilera.halt_flag import HaltFlag
from enfilera.lines import Line
from enfilera.openness_service import OpennessService
from enfilera.preferences_store import LinePreferenceStore
from enfilera.samples_store import SampleStore
from enfilera.submission_recorder import SubmissionRecorder
from enfilera.submissions_store import SubmissionStore
from enfilera.timer_handlers import RegisterTimer

SP = ZoneInfo("America/Sao_Paulo")
LINES = (Line("card", "Cartão"), Line("pix", "Pix"))
USER = 7
START = datetime(2026, 6, 30, 12, 5, tzinfo=SP)
MIDNIGHT = datetime(2026, 6, 30, 0, 0, tzinfo=SP)
CENTER = (-23.559616, -46.731386)
FAR = (-23.5, -46.7)


def _run(coro: Coroutine[Any, Any, None]) -> None:
    asyncio.run(coro)


class Clock:
    """A test clock the flow advances between start and stop."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _config() -> EstimationConfig:
    return EstimationConfig(min_samples=3, clamp_min=60, clamp_max=3600, mad_k=3.0)


def _timer(conn: sqlite3.Connection, clock: Clock) -> RegisterTimer:
    schedule = _schedule()
    openness = OpennessService(schedule, ClosureStore(conn), HaltFlag(conn))
    recorder = SubmissionRecorder(SampleStore(conn), SubmissionStore(conn), schedule)
    return RegisterTimer(
        LINES,
        LinePreferenceStore(conn),
        openness,
        recorder,
        Geofence(*CENTER, 50),
        _config(),
        clock,
    )


def _cmd() -> FakeUpdate:
    return FakeUpdate(effective_message=FakeMessage(), effective_user=FakeUser(USER))


def _location(lat: float, lon: float) -> FakeUpdate:
    message = FakeMessage(location=FakeLocation(lat, lon))
    return FakeUpdate(effective_message=message, effective_user=FakeUser(USER))


def _last_reply(update: FakeUpdate) -> str:
    return update.effective_message.replies[-1][0]


def _pick_card(conn: sqlite3.Connection) -> None:
    LinePreferenceStore(conn).set_line(USER, "card")


# --- start gate -----------------------------------------------------------


def test_start_prompts_for_location_when_open(memory_db: sqlite3.Connection) -> None:
    _pick_card(memory_db)
    update, context = _cmd(), FakeContext()
    _run(_timer(memory_db, Clock(START)).start(update, context))
    text, markup = update.effective_message.replies[-1]
    assert "localização" in text
    assert isinstance(markup, ReplyKeyboardMarkup)
    assert context.user_data["awaiting_line"] == "card"


def test_start_prompt_reassures_location_is_not_stored(
    memory_db: sqlite3.Connection,
) -> None:
    # Users balk at sharing location; the prompt must say why it is asked and
    # that it is discarded, or we lose contributors to a privacy worry.
    _pick_card(memory_db)
    update, context = _cmd(), FakeContext()
    _run(_timer(memory_db, Clock(START)).start(update, context))
    text = update.effective_message.replies[-1][0]
    assert "confirmar que você está no restaurante" in text  # only for verification
    assert "nunca guarda" in text  # and never stored


def test_start_rejects_when_no_line(memory_db: sqlite3.Connection) -> None:
    update = _cmd()
    _run(_timer(memory_db, Clock(START)).start(update, FakeContext()))
    assert "/fila" in _last_reply(update)


def test_start_rejects_when_closed(memory_db: sqlite3.Connection) -> None:
    _pick_card(memory_db)
    HaltFlag(memory_db).set(True)
    update = _cmd()
    _run(_timer(memory_db, Clock(START)).start(update, FakeContext()))
    assert "Fechado" in _last_reply(update)


def test_start_rejects_when_already_submitted(memory_db: sqlite3.Connection) -> None:
    _pick_card(memory_db)
    SubmissionStore(memory_db).mark(USER, date(2026, 6, 30), "lunch", "card")
    update = _cmd()
    _run(_timer(memory_db, Clock(START)).start(update, FakeContext()))
    assert "já registrou" in _last_reply(update)


# --- geofence -------------------------------------------------------------


def test_location_inside_radius_starts_timer(memory_db: sqlite3.Connection) -> None:
    _pick_card(memory_db)
    context = FakeContext()
    timer = _timer(memory_db, Clock(START))
    _run(timer.start(_cmd(), context))
    loc = _location(*CENTER)
    _run(timer.on_location(loc, context))
    assert context.user_data["timer_start"] == START
    assert context.user_data["timer_line"] == "card"
    assert "awaiting_line" not in context.user_data
    assert "Cronômetro iniciado" in _last_reply(loc)


def test_location_outside_radius_is_rejected(memory_db: sqlite3.Connection) -> None:
    _pick_card(memory_db)
    context = FakeContext()
    timer = _timer(memory_db, Clock(START))
    _run(timer.start(_cmd(), context))
    loc = _location(*FAR)
    _run(timer.on_location(loc, context))
    assert "restaurante" in _last_reply(loc)
    assert "timer_start" not in context.user_data
    assert context.user_data["awaiting_line"] == "card"  # can retry closer


def test_location_without_start_hints_to_register(
    memory_db: sqlite3.Connection,
) -> None:
    loc = _location(*CENTER)
    _run(_timer(memory_db, Clock(START)).on_location(loc, FakeContext()))
    assert "/registrar" in _last_reply(loc)


# --- stop / submit --------------------------------------------------------


def _started(
    conn: sqlite3.Connection, clock: Clock
) -> tuple[RegisterTimer, FakeContext]:
    _pick_card(conn)
    context = FakeContext()
    timer = _timer(conn, clock)
    _run(timer.start(_cmd(), context))
    _run(timer.on_location(_location(*CENTER), context))
    return timer, context


def _decision(data: str) -> FakeUpdate:
    return FakeUpdate(
        callback_query=FakeCallbackQuery(data), effective_user=FakeUser(USER)
    )


def _samples(conn: sqlite3.Connection) -> list[int]:
    return _samples_for(conn, "card")


def _samples_for(conn: sqlite3.Connection, line_id: str) -> list[int]:
    return SampleStore(conn).values_in_window(line_id, 2, time(12, 0), MIDNIGHT)


def _callback_data(markup: InlineKeyboardMarkup) -> list[str]:
    """Every button's callback_data, flattened across the keyboard's rows."""
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_stop_asks_to_confirm_without_recording_yet(
    memory_db: sqlite3.Connection,
) -> None:
    clock = Clock(START)
    timer, context = _started(memory_db, clock)
    clock.now = START + timedelta(minutes=12)  # 720s transit
    stop = _cmd()
    _run(timer.stop(stop, context))
    text, markup = stop.effective_message.replies[-1]
    assert "~12 min" in text
    assert isinstance(markup, InlineKeyboardMarkup)
    assert context.user_data["pending_seconds"] == 720
    assert _samples(memory_db) == []  # nothing recorded until confirmed


def test_confirm_records_sample_and_burns_period(
    memory_db: sqlite3.Connection,
) -> None:
    clock = Clock(START)
    timer, context = _started(memory_db, clock)
    clock.now = START + timedelta(minutes=12)
    _run(timer.stop(_cmd(), context))
    confirm = _decision("timer:confirm")
    _run(timer.on_decision(confirm, context))
    assert "~12 min" in confirm.callback_query.edits[-1]
    assert _samples(memory_db) == [720]
    assert SubmissionStore(memory_db).has_submitted(USER, date(2026, 6, 30), "lunch")
    assert "timer_start" not in context.user_data


def test_resume_keeps_original_timer_then_records_true_total(
    memory_db: sqlite3.Connection,
) -> None:
    # The scenario: a premature /parar at 10 min, resumed, then the real stop
    # at 20 min — the recorded value must be the true 20 min, not the early 10.
    clock = Clock(START)
    timer, context = _started(memory_db, clock)
    clock.now = START + timedelta(minutes=10)
    _run(timer.stop(_cmd(), context))
    resume = _decision("timer:resume")
    _run(timer.on_decision(resume, context))
    assert "retomado" in resume.callback_query.edits[-1]
    assert context.user_data["timer_start"] == START  # still running from join
    assert "pending_seconds" not in context.user_data
    clock.now = START + timedelta(minutes=20)
    _run(timer.stop(_cmd(), context))
    _run(timer.on_decision(_decision("timer:confirm"), context))
    assert _samples(memory_db) == [1200]  # 20 min, not 10


def test_confirm_rejects_too_short(memory_db: sqlite3.Connection) -> None:
    clock = Clock(START)
    timer, context = _started(memory_db, clock)
    clock.now = START + timedelta(seconds=30)  # under the 1-min clamp
    _run(timer.stop(_cmd(), context))
    confirm = _decision("timer:confirm")
    _run(timer.on_decision(confirm, context))
    reject = confirm.callback_query.edits[-1]
    assert "curto" in reject
    assert "mínimo 1 min" in reject  # named from config.clamp_min, not hardcoded
    assert _samples(memory_db) == []


def test_confirm_rejects_too_long(memory_db: sqlite3.Connection) -> None:
    clock = Clock(START)
    timer, context = _started(memory_db, clock)
    clock.now = START + timedelta(hours=2)  # over the 60-min ceiling
    _run(timer.stop(_cmd(), context))
    confirm = _decision("timer:confirm")
    _run(timer.on_decision(confirm, context))
    assert "longo" in confirm.callback_query.edits[-1]
    assert _samples(memory_db) == []


def test_stop_without_active_timer(memory_db: sqlite3.Connection) -> None:
    stop = _cmd()
    _run(_timer(memory_db, Clock(START)).stop(stop, FakeContext()))
    assert "não tem um cronômetro" in _last_reply(stop)


# --- line naming + trocar de fila -----------------------------------------


def test_started_message_names_the_picked_line(
    memory_db: sqlite3.Connection,
) -> None:
    # The user must see which line the running timer is attributed to, so a
    # wrong default is caught before /parar (feedback: "Cronômetro Iniciado"
    # should show the line picked).
    _pick_card(memory_db)
    context = FakeContext()
    timer = _timer(memory_db, Clock(START))
    _run(timer.start(_cmd(), context))
    loc = _location(*CENTER)
    _run(timer.on_location(loc, context))
    text = _last_reply(loc)
    assert "Cronômetro iniciado" in text
    assert "Cartão" in text


def test_confirm_prompt_names_the_line(memory_db: sqlite3.Connection) -> None:
    clock = Clock(START)
    timer, context = _started(memory_db, clock)
    clock.now = START + timedelta(minutes=12)
    stop = _cmd()
    _run(timer.stop(stop, context))
    text = _last_reply(stop)
    assert "~12 min" in text
    assert "Cartão" in text  # the line the sample is about


def test_switch_shows_the_line_picker(memory_db: sqlite3.Connection) -> None:
    clock = Clock(START)
    timer, context = _started(memory_db, clock)
    clock.now = START + timedelta(minutes=12)
    _run(timer.stop(_cmd(), context))
    switch = _decision("timer:switch")
    _run(timer.on_decision(switch, context))
    markup = switch.callback_query.edit_markups[-1]
    assert isinstance(markup, InlineKeyboardMarkup)
    assert _callback_data(markup) == ["timer:line:card", "timer:line:pix"]
    assert context.user_data["pending_seconds"] == 720  # not recorded, not lost


def test_switch_reattributes_pending_and_reshows_confirm(
    memory_db: sqlite3.Connection,
) -> None:
    clock = Clock(START)
    timer, context = _started(memory_db, clock)
    clock.now = START + timedelta(minutes=12)
    _run(timer.stop(_cmd(), context))
    _run(timer.on_decision(_decision("timer:switch"), context))
    picked = _decision("timer:line:pix")
    _run(timer.on_decision(picked, context))
    assert context.user_data["timer_line"] == "pix"
    text = picked.callback_query.edits[-1]
    assert "~12 min" in text
    assert "Pix" in text
    # The confirm choice is offered again so the user still commits explicitly.
    markup = picked.callback_query.edit_markups[-1]
    assert isinstance(markup, InlineKeyboardMarkup)
    assert "timer:confirm" in _callback_data(markup)


def test_confirm_after_switch_records_to_the_new_line(
    memory_db: sqlite3.Connection,
) -> None:
    clock = Clock(START)
    timer, context = _started(memory_db, clock)  # started on "card"
    clock.now = START + timedelta(minutes=12)
    _run(timer.stop(_cmd(), context))
    _run(timer.on_decision(_decision("timer:switch"), context))
    _run(timer.on_decision(_decision("timer:line:pix"), context))
    _run(timer.on_decision(_decision("timer:confirm"), context))
    assert _samples_for(memory_db, "pix") == [720]
    assert _samples_for(memory_db, "card") == []  # not the original line


def test_switch_does_not_change_saved_line_preference(
    memory_db: sqlite3.Connection,
) -> None:
    # Trocar de fila re-attributes only the current registration; the user's
    # tracked /fila line is a separate setting and must stay put.
    clock = Clock(START)
    timer, context = _started(memory_db, clock)  # preference is "card"
    clock.now = START + timedelta(minutes=12)
    _run(timer.stop(_cmd(), context))
    _run(timer.on_decision(_decision("timer:switch"), context))
    _run(timer.on_decision(_decision("timer:line:pix"), context))
    _run(timer.on_decision(_decision("timer:confirm"), context))
    assert LinePreferenceStore(memory_db).get_line(USER) == "card"


def test_decision_keyboard_offers_confirm_resume_and_switch(
    memory_db: sqlite3.Connection,
) -> None:
    clock = Clock(START)
    timer, context = _started(memory_db, clock)
    clock.now = START + timedelta(minutes=12)
    stop = _cmd()
    _run(timer.stop(stop, context))
    markup = stop.effective_message.replies[-1][1]
    assert _callback_data(markup) == ["timer:confirm", "timer:resume", "timer:switch"]


def test_register_adds_start_stop_location_and_decision_handlers(
    memory_db: sqlite3.Connection,
) -> None:
    app = ApplicationBuilder().token("123:abc").job_queue(None).build()
    _timer(memory_db, Clock(START)).register(app)
    registered = app.handlers[0]
    assert sum(isinstance(h, CommandHandler) for h in registered) == 2
    assert any(isinstance(h, MessageHandler) for h in registered)
    assert any(isinstance(h, CallbackQueryHandler) for h in registered)
