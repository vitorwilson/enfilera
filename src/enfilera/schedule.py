"""Pure time geometry for the cafeteria calendar.

No I/O, no clock, no Telegram/DB imports: this module only turns a parsed
config mapping into validated value objects and answers pure questions about
where a time-of-day falls — which period, which block. Operational state
(closures, halt, operating day) is layered on top in ``openness.py``.

Periods are half-open ``[start, end)``: the opening minute is in the period,
the closing minute is not. Blocks are clock-aligned buckets of
``block_minutes`` keyed by their start time-of-day (the ``11:00–12:00``
bucket), so the same (line, weekday, block) bucket is stable across days.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import time
from itertools import pairwise
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class Period:
    """A named operating window within a day, half-open ``[start, end)``."""

    id: str
    start: time
    end: time

    def contains(self, moment: time) -> bool:
        return self.start <= moment < self.end


@dataclass(frozen=True)
class Block:
    """A clock-aligned bucket of ``block_minutes``, keyed by its start
    time-of-day. ``Block(time(11, 0))`` is the 11:00–12:00 bucket at a
    60-minute block size."""

    start: time


@dataclass(frozen=True)
class Schedule:
    """Validated operating schedule for one cafeteria."""

    timezone: ZoneInfo
    operating_days: frozenset[int]
    block_minutes: int
    periods: tuple[Period, ...]


def build_schedule(raw: Mapping[str, object]) -> Schedule:
    """Parse and validate a config mapping (what ``tomllib`` produces).

    >>> build_schedule({
    ...     "restaurant": {"timezone": "America/Sao_Paulo"},
    ...     "schedule": {"operating_days": [1], "block_minutes": 60,
    ...                  "periods": [{"id": "lunch", "start": "10:30",
    ...                               "end": "14:30"}]},
    ... }).block_minutes
    60
    """
    restaurant = _section(raw, "restaurant")
    schedule = _section(raw, "schedule")
    return Schedule(
        timezone=_parse_timezone(restaurant["timezone"]),
        operating_days=_parse_operating_days(schedule["operating_days"]),
        block_minutes=_parse_block_minutes(schedule["block_minutes"]),
        periods=_parse_periods(schedule["periods"]),
    )


# --- parsing helpers -----------------------------------------------------


def _section(raw: Mapping[str, object], name: str) -> Mapping[str, object]:
    section = raw.get(name)
    if not isinstance(section, Mapping):
        raise ValueError(f"config section [{name}] is missing, got {section!r}")
    return section


def _parse_timezone(name: object) -> ZoneInfo:
    try:
        return ZoneInfo(str(name))
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone {name!r}") from exc


def _parse_operating_days(days: object) -> frozenset[int]:
    if not isinstance(days, Iterable) or isinstance(days, (str, bytes)):
        raise ValueError(f"operating_days must be a list of 1..7, got {days!r}")
    result = frozenset(days)
    if not result:
        raise ValueError("operating_days must not be empty")
    for day in result:
        if not isinstance(day, int) or isinstance(day, bool) or not 1 <= day <= 7:
            raise ValueError(f"operating day must be ISO weekday 1..7, got {day}")
    return result


def _parse_block_minutes(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"block_minutes must be a positive integer, got {value!r}")
    return value


def _parse_periods(items: object) -> tuple[Period, ...]:
    if not isinstance(items, Iterable) or not list(items):
        raise ValueError(f"schedule must define at least one period, got {items!r}")
    periods = tuple(_parse_period(item) for item in items)
    _reject_duplicate_ids(periods)
    _reject_overlaps(periods)
    return periods


def _parse_period(item: Mapping[str, str]) -> Period:
    start = _parse_hhmm(item["start"])
    end = _parse_hhmm(item["end"])
    if start >= end:
        raise ValueError(
            f"period {item['id']!r} start must precede end, "
            f"got {item['start']}–{item['end']}"
        )
    return Period(id=str(item["id"]), start=start, end=end)


def _parse_hhmm(value: object) -> time:
    parts = str(value).split(":")
    if len(parts) != 2 or not all(p.isdigit() and len(p) == 2 for p in parts):
        raise ValueError(f"time must be 'HH:MM', got {value!r}")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError(f"time out of range 'HH:MM', got {value!r}")
    return time(hour, minute)


def _reject_duplicate_ids(periods: tuple[Period, ...]) -> None:
    seen: set[str] = set()
    for period in periods:
        if period.id in seen:
            raise ValueError(f"duplicate period id {period.id!r}")
        seen.add(period.id)


def _reject_overlaps(periods: tuple[Period, ...]) -> None:
    ordered = sorted(periods, key=lambda p: p.start)
    for earlier, later in pairwise(ordered):
        if later.start < earlier.end:
            raise ValueError(
                f"periods overlap: {earlier.id!r} ends {earlier.end}, "
                f"{later.id!r} starts {later.start}"
            )


# --- pure geometry queries -----------------------------------------------


def period_containing(moment: time, schedule: Schedule) -> Period | None:
    """The period whose ``[start, end)`` contains ``moment``, else ``None``."""
    for period in schedule.periods:
        if period.contains(moment):
            return period
    return None


def block_for(moment: time, schedule: Schedule) -> Block:
    """The clock-aligned block that ``moment`` falls into."""
    aligned = (_minutes(moment) // schedule.block_minutes) * schedule.block_minutes
    return _block_at(aligned)


def previous_block(block: Block, period: Period, schedule: Schedule) -> Block | None:
    """The block one step earlier, if it still overlaps ``period``.

    Used by confidence gating: when today's current block is too sparse, fall
    back to the previous block of the same period. Returns ``None`` for the
    period's first block (nothing earlier belongs to it).
    """
    prev_start = _minutes(block.start) - schedule.block_minutes
    if prev_start < 0:
        return None
    candidate = _block_at(prev_start)
    if not _overlaps_period(candidate, period, schedule):
        return None
    return candidate


def _overlaps_period(block: Block, period: Period, schedule: Schedule) -> bool:
    block_start = _minutes(block.start)
    block_end = block_start + schedule.block_minutes
    return block_start < _minutes(period.end) and block_end > _minutes(period.start)


def _block_at(start_minutes: int) -> Block:
    return Block(start=time(start_minutes // 60, start_minutes % 60))


def _minutes(moment: time) -> int:
    return moment.hour * 60 + moment.minute
