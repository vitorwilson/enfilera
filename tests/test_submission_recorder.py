"""Tests for the submission recorder.

Buckets a finished transit into the block its *start* (queue-join) falls in,
stores the sample, and marks the one-per-period flag — all from server time.
2026-06-30 is a Tuesday; lunch is 10:30-14:30, blocks align to the clock hour.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, time
from zoneinfo import ZoneInfo

from enfilera.samples_store import SampleStore
from enfilera.schedule import build_schedule
from enfilera.submission_recorder import SubmissionRecorder
from enfilera.submissions_store import SubmissionStore

SP = ZoneInfo("America/Sao_Paulo")
USER = 7
MIDNIGHT = datetime(2026, 6, 30, 0, 0, tzinfo=SP)


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


def _recorder(conn: sqlite3.Connection) -> SubmissionRecorder:
    return SubmissionRecorder(SampleStore(conn), SubmissionStore(conn), _schedule())


def _sp(hour: int, minute: int) -> datetime:
    return datetime(2026, 6, 30, hour, minute, tzinfo=SP)


def test_record_stores_sample_in_the_start_block(memory_db: sqlite3.Connection) -> None:
    _recorder(memory_db).record(USER, "card", _sp(12, 5), 600)
    values = SampleStore(memory_db).values_in_window("card", 2, time(12, 0), MIDNIGHT)
    assert values == [600]


def test_buckets_by_start_block_not_clock_now(memory_db: sqlite3.Connection) -> None:
    _recorder(memory_db).record(USER, "card", _sp(11, 50), 600)
    store = SampleStore(memory_db)
    assert store.values_in_window("card", 2, time(11, 0), MIDNIGHT) == [600]
    assert store.values_in_window("card", 2, time(12, 0), MIDNIGHT) == []


def test_record_marks_the_start_period(memory_db: sqlite3.Connection) -> None:
    recorder = _recorder(memory_db)
    assert recorder.already_submitted(USER, _sp(12, 5)) is False
    recorder.record(USER, "card", _sp(12, 5), 600)
    assert recorder.already_submitted(USER, _sp(12, 5)) is True


def test_other_period_is_still_open(memory_db: sqlite3.Connection) -> None:
    recorder = _recorder(memory_db)
    recorder.record(USER, "card", _sp(12, 5), 600)  # marks lunch
    assert recorder.already_submitted(USER, _sp(18, 5)) is False  # dinner


def test_already_submitted_is_per_user(memory_db: sqlite3.Connection) -> None:
    recorder = _recorder(memory_db)
    recorder.record(USER, "card", _sp(12, 5), 600)
    assert recorder.already_submitted(99, _sp(12, 5)) is False
