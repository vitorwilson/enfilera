"""Operational openness: is the cafeteria taking timers right now, and why?

Layers operational state on top of the pure geometry in ``schedule.py``: the
halt flag, the operating-day list, and active closure records. The result is a
small tagged union — ``OpenStatus`` (with the live period + block) or
``ClosedStatus`` (with a machine-readable reason for the admin status command
and the user-facing closed message).

``now`` must be timezone-aware server time; it is localized to the configured
zone here so a user's device clock can never move a period boundary.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import ClassVar

from enfilera.closures import Closure, period_closure, whole_day_closure
from enfilera.schedule import Block, Schedule, block_for, period_containing


class ClosedReason(Enum):
    """Why the cafeteria is closed, in precedence order of the check."""

    HALTED = "halted"
    NON_OPERATING_DAY = "non_operating_day"
    CLOSURE = "closure"
    OUTSIDE_PERIODS = "outside_periods"


@dataclass(frozen=True)
class OpenStatus:
    """Open: the live period and the block samples land in right now."""

    period_id: str
    block: Block

    is_open: ClassVar[bool] = True


@dataclass(frozen=True)
class ClosedStatus:
    """Closed: the reason, plus an optional human label (e.g. closure reason)."""

    reason: ClosedReason
    detail: str | None = None

    is_open: ClassVar[bool] = False


Status = OpenStatus | ClosedStatus


@dataclass(frozen=True)
class PeriodInstance:
    """A period on a specific date — the key for the one-per-period rule."""

    date: date
    period_id: str


def status_at(
    now: datetime,
    schedule: Schedule,
    closures: Iterable[Closure],
    halted: bool,
) -> Status:
    """Resolve the open/closed status at ``now`` (timezone-aware server time).

    >>> # See tests/test_openness.py for worked examples across the precedence:
    >>> # halt -> non-operating day -> closure -> outside periods -> open.
    """
    local = _localize(now, schedule)
    if halted:
        return ClosedStatus(ClosedReason.HALTED)
    if local.isoweekday() not in schedule.operating_days:
        return ClosedStatus(ClosedReason.NON_OPERATING_DAY)
    records = list(closures)
    whole_day = whole_day_closure(local.date(), records)
    if whole_day is not None:
        return ClosedStatus(ClosedReason.CLOSURE, whole_day.reason)
    period = period_containing(local.time(), schedule)
    if period is None:
        return ClosedStatus(ClosedReason.OUTSIDE_PERIODS)
    shut = period_closure(local.date(), period.id, records)
    if shut is not None:
        return ClosedStatus(ClosedReason.CLOSURE, shut.reason)
    return OpenStatus(period.id, block_for(local.time(), schedule))


def current_period(now: datetime, schedule: Schedule) -> PeriodInstance | None:
    """The (date, period) we are in by the clock, for the one-per-period rule.

    Geometry only — the caller gates the actual submission on ``status_at``.
    """
    local = _localize(now, schedule)
    period = period_containing(local.time(), schedule)
    if period is None:
        return None
    return PeriodInstance(local.date(), period.id)


def _localize(now: datetime, schedule: Schedule) -> datetime:
    if now.tzinfo is None:
        raise ValueError(f"now must be timezone-aware server time, got naive {now!r}")
    return now.astimezone(schedule.timezone)
