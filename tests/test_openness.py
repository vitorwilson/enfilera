"""Tests for the operational openness check.

Combines operating-day, time geometry, closures, and the halt flag into a
single "open right now?" answer. All times are server-obtained and
timezone-aware; the engine localizes them to the configured zone (so DST is
handled by zoneinfo, never by the caller's device clock).

Fixed dates used below: 2026-06-30 and 2026-01-06 are both Tuesdays
(operating days); 2026-07-04 is a Saturday, 2026-07-05 a Sunday.
"""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from schedules import make_schedule as _schedule

from enfilera.closures import Closure
from enfilera.openness import (
    ClosedReason,
    ClosedStatus,
    OpenStatus,
    PeriodInstance,
    current_period,
    status_at,
)
from enfilera.schedule import Block

SP = ZoneInfo("America/Sao_Paulo")


def _sp(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SP)


# --- open cases ----------------------------------------------------------


def test_open_during_lunch_reports_period_and_block() -> None:
    status = status_at(_sp(2026, 6, 30, 12, 15), _schedule(), [], halted=False)
    assert status.is_open
    assert isinstance(status, OpenStatus)
    assert status.period_id == "lunch"
    assert status.block == Block(time(12, 0))


def test_open_at_exact_period_start() -> None:
    status = status_at(_sp(2026, 6, 30, 10, 30), _schedule(), [], halted=False)
    assert status.is_open
    assert isinstance(status, OpenStatus)
    assert status.block == Block(time(10, 0))


def test_open_during_dinner_reports_dinner_block() -> None:
    status = status_at(_sp(2026, 6, 30, 18, 15), _schedule(), [], halted=False)
    assert isinstance(status, OpenStatus)
    assert status.period_id == "dinner"
    assert status.block == Block(time(18, 0))


# --- closed: geometry ----------------------------------------------------


def test_closed_at_exact_period_end() -> None:
    status = status_at(_sp(2026, 6, 30, 14, 30), _schedule(), [], halted=False)
    assert not status.is_open
    assert isinstance(status, ClosedStatus)
    assert status.reason == ClosedReason.OUTSIDE_PERIODS


def test_closed_between_periods() -> None:
    status = status_at(_sp(2026, 6, 30, 15, 30), _schedule(), [], halted=False)
    assert isinstance(status, ClosedStatus)
    assert status.reason == ClosedReason.OUTSIDE_PERIODS


def test_closed_on_saturday() -> None:
    status = status_at(_sp(2026, 7, 4, 12, 0), _schedule(), [], halted=False)
    assert isinstance(status, ClosedStatus)
    assert status.reason == ClosedReason.NON_OPERATING_DAY


def test_closed_on_sunday() -> None:
    status = status_at(_sp(2026, 7, 5, 12, 0), _schedule(), [], halted=False)
    assert isinstance(status, ClosedStatus)
    assert status.reason == ClosedReason.NON_OPERATING_DAY


# --- closed: halt & closures (precedence) --------------------------------


def test_halt_overrides_open_hours() -> None:
    status = status_at(_sp(2026, 6, 30, 12, 0), _schedule(), [], halted=True)
    assert isinstance(status, ClosedStatus)
    assert status.reason == ClosedReason.HALTED


def test_whole_day_closure_closes_lunch_with_reason() -> None:
    closures = [Closure(date(2026, 6, 30), period_id=None, reason="feriado")]
    status = status_at(_sp(2026, 6, 30, 12, 0), _schedule(), closures, halted=False)
    assert isinstance(status, ClosedStatus)
    assert status.reason == ClosedReason.CLOSURE
    assert status.detail == "feriado"


def test_whole_day_closure_reported_even_between_periods() -> None:
    closures = [Closure(date(2026, 6, 30), period_id=None, reason="feriado")]
    status = status_at(_sp(2026, 6, 30, 15, 30), _schedule(), closures, halted=False)
    assert isinstance(status, ClosedStatus)
    assert status.reason == ClosedReason.CLOSURE


def test_single_period_closure_shuts_only_that_period() -> None:
    closures = [Closure(date(2026, 6, 30), period_id="lunch", reason="sem almoço")]
    lunch = status_at(_sp(2026, 6, 30, 12, 0), _schedule(), closures, halted=False)
    dinner = status_at(_sp(2026, 6, 30, 18, 0), _schedule(), closures, halted=False)
    assert isinstance(lunch, ClosedStatus)
    assert lunch.reason == ClosedReason.CLOSURE and lunch.detail == "sem almoço"
    assert dinner.is_open
    assert isinstance(dinner, OpenStatus) and dinner.period_id == "dinner"


def test_closure_on_other_date_is_ignored() -> None:
    closures = [Closure(date(2026, 7, 1), period_id=None)]
    status = status_at(_sp(2026, 6, 30, 12, 0), _schedule(), closures, halted=False)
    assert status.is_open


# --- input contract & timezone/DST ---------------------------------------


def test_naive_now_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        status_at(datetime(2026, 6, 30, 12, 0), _schedule(), [], halted=False)


def test_dst_summer_localizes_to_open() -> None:
    # 15:00Z in late June is 11:00 EDT (UTC-4) -> inside lunch.
    schedule = _schedule("America/New_York")
    status = status_at(datetime(2026, 6, 30, 15, 0, tzinfo=UTC), schedule, [], False)
    assert isinstance(status, OpenStatus)
    assert status.period_id == "lunch"


def test_dst_winter_localizes_to_closed() -> None:
    # Same 15:00Z in January is 10:00 EST (UTC-5) -> before lunch opens.
    schedule = _schedule("America/New_York")
    status = status_at(datetime(2026, 1, 6, 15, 0, tzinfo=UTC), schedule, [], False)
    assert isinstance(status, ClosedStatus)
    assert status.reason == ClosedReason.OUTSIDE_PERIODS


# --- current_period: one-submission-per-period identity ------------------


def test_current_period_identity_during_lunch() -> None:
    instance = current_period(_sp(2026, 6, 30, 12, 0), _schedule())
    assert instance == PeriodInstance(date(2026, 6, 30), "lunch")


def test_current_period_is_none_between_periods() -> None:
    assert current_period(_sp(2026, 6, 30, 15, 30), _schedule()) is None
