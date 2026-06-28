"""Tests for the pure time geometry: config parsing, periods, blocks.

No I/O, no clock — every input is constructed in the test. These cover the
boundary cases called out in docs/PLAN.md Feature 1: exact period edges,
between-period gaps, clock-aligned blocks, and the previous-block lookup.
"""

from datetime import time

import pytest

from enfilera.schedule import (
    Block,
    block_for,
    build_schedule,
    period_containing,
    previous_block,
)


def _raw_config() -> dict:
    """A minimal valid config mapping (what tomllib would produce)."""
    return {
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


# --- build_schedule: happy path ------------------------------------------


def test_build_schedule_parses_periods_and_block_size() -> None:
    schedule = build_schedule(_raw_config())

    assert schedule.block_minutes == 60
    assert schedule.operating_days == frozenset({1, 2, 3, 4, 5})
    assert [p.id for p in schedule.periods] == ["lunch", "dinner"]
    assert schedule.periods[0].start == time(10, 30)
    assert schedule.periods[0].end == time(14, 30)
    assert str(schedule.timezone) == "America/Sao_Paulo"


# --- build_schedule: validation ------------------------------------------


def test_build_schedule_rejects_start_not_before_end() -> None:
    raw = _raw_config()
    raw["schedule"]["periods"][0]["end"] = "10:30"  # equal to start
    with pytest.raises(ValueError, match="10:30"):
        build_schedule(raw)


def test_build_schedule_rejects_overlapping_periods() -> None:
    raw = _raw_config()
    raw["schedule"]["periods"][1]["start"] = "14:00"  # overlaps lunch end 14:30
    with pytest.raises(ValueError, match="overlap"):
        build_schedule(raw)


def test_build_schedule_rejects_duplicate_period_ids() -> None:
    raw = _raw_config()
    raw["schedule"]["periods"][1]["id"] = "lunch"
    with pytest.raises(ValueError, match="lunch"):
        build_schedule(raw)


def test_build_schedule_rejects_empty_periods() -> None:
    raw = _raw_config()
    raw["schedule"]["periods"] = []
    with pytest.raises(ValueError, match="period"):
        build_schedule(raw)


@pytest.mark.parametrize("bad", ["25:00", "10:60", "abc", "1030", "10:5"])
def test_build_schedule_rejects_malformed_time(bad: str) -> None:
    raw = _raw_config()
    raw["schedule"]["periods"][0]["start"] = bad
    with pytest.raises(ValueError, match=bad):
        build_schedule(raw)


@pytest.mark.parametrize("bad_day", [0, 8, -1])
def test_build_schedule_rejects_out_of_range_weekday(bad_day: int) -> None:
    raw = _raw_config()
    raw["schedule"]["operating_days"] = [bad_day]
    with pytest.raises(ValueError, match=str(bad_day)):
        build_schedule(raw)


def test_build_schedule_rejects_non_positive_block_minutes() -> None:
    raw = _raw_config()
    raw["schedule"]["block_minutes"] = 0
    with pytest.raises(ValueError, match="block_minutes"):
        build_schedule(raw)


def test_build_schedule_rejects_unknown_timezone() -> None:
    raw = _raw_config()
    raw["restaurant"]["timezone"] = "Mars/Olympus_Mons"
    with pytest.raises(ValueError, match="Mars/Olympus_Mons"):
        build_schedule(raw)


# --- period_containing: half-open [start, end) ---------------------------


def test_period_containing_start_is_inclusive() -> None:
    schedule = build_schedule(_raw_config())
    assert period_containing(time(10, 30), schedule).id == "lunch"


def test_period_containing_end_is_exclusive() -> None:
    schedule = build_schedule(_raw_config())
    assert period_containing(time(14, 30), schedule) is None


def test_period_containing_just_before_end_is_inside() -> None:
    schedule = build_schedule(_raw_config())
    assert period_containing(time(14, 29), schedule).id == "lunch"


def test_period_containing_between_periods_is_none() -> None:
    schedule = build_schedule(_raw_config())
    assert period_containing(time(15, 0), schedule) is None


def test_period_containing_second_period() -> None:
    schedule = build_schedule(_raw_config())
    assert period_containing(time(17, 0), schedule).id == "dinner"


def test_period_containing_before_opening_is_none() -> None:
    schedule = build_schedule(_raw_config())
    assert period_containing(time(9, 0), schedule) is None


# --- block_for: clock-aligned buckets ------------------------------------


@pytest.mark.parametrize(
    "moment,expected_start",
    [
        (time(10, 35), time(10, 0)),  # partial first block aligns to 10:00
        (time(11, 0), time(11, 0)),
        (time(11, 59), time(11, 0)),
        (time(14, 29), time(14, 0)),
        (time(17, 0), time(17, 0)),
    ],
)
def test_block_for_aligns_to_clock(moment: time, expected_start: time) -> None:
    schedule = build_schedule(_raw_config())
    assert block_for(moment, schedule) == Block(start=expected_start)


def test_block_for_respects_block_minutes() -> None:
    raw = _raw_config()
    raw["schedule"]["block_minutes"] = 30
    schedule = build_schedule(raw)
    assert block_for(time(11, 29), schedule) == Block(start=time(11, 0))
    assert block_for(time(11, 30), schedule) == Block(start=time(11, 30))


# --- previous_block: confidence-gating fallback --------------------------


def test_previous_block_within_period() -> None:
    schedule = build_schedule(_raw_config())
    lunch = schedule.periods[0]
    assert previous_block(Block(time(11, 0)), lunch, schedule) == Block(time(10, 0))


def test_previous_block_of_first_block_is_none() -> None:
    schedule = build_schedule(_raw_config())
    lunch = schedule.periods[0]
    # 10:00 is lunch's first (partial) block; nothing earlier belongs to lunch.
    assert previous_block(Block(time(10, 0)), lunch, schedule) is None


def test_previous_block_mid_period() -> None:
    schedule = build_schedule(_raw_config())
    lunch = schedule.periods[0]
    assert previous_block(Block(time(14, 0)), lunch, schedule) == Block(time(13, 0))
