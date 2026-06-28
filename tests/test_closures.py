"""Tests for closure value objects and their pure active-lookups.

A closure is always a single day here; ranges are expanded to one record per
day at the persistence layer (docs/PLAN.md). ``period_id is None`` means the
whole day is shut; otherwise only that one period.
"""

from datetime import date

from enfilera.closures import Closure, period_closure, whole_day_closure

A_DAY = date(2026, 6, 30)
NEXT_DAY = date(2026, 7, 1)


def test_whole_day_closure_matches_null_period() -> None:
    closures = [Closure(A_DAY, period_id=None, reason="feriado")]
    found = whole_day_closure(A_DAY, closures)
    assert found is not None and found.reason == "feriado"


def test_whole_day_closure_ignores_period_specific_record() -> None:
    closures = [Closure(A_DAY, period_id="lunch", reason="sem almoço")]
    assert whole_day_closure(A_DAY, closures) is None


def test_whole_day_closure_other_date_is_none() -> None:
    closures = [Closure(NEXT_DAY, period_id=None)]
    assert whole_day_closure(A_DAY, closures) is None


def test_period_closure_matches_that_period() -> None:
    closures = [Closure(A_DAY, period_id="lunch", reason="sem almoço")]
    found = period_closure(A_DAY, "lunch", closures)
    assert found is not None and found.reason == "sem almoço"


def test_period_closure_other_period_is_none() -> None:
    closures = [Closure(A_DAY, period_id="lunch")]
    assert period_closure(A_DAY, "dinner", closures) is None


def test_period_closure_does_not_match_whole_day_record() -> None:
    # whole-day records are handled separately by whole_day_closure; this
    # period-specific lookup must not silently match a None period.
    closures = [Closure(A_DAY, period_id=None)]
    assert period_closure(A_DAY, "lunch", closures) is None


def test_lookups_on_empty_collection() -> None:
    assert whole_day_closure(A_DAY, []) is None
    assert period_closure(A_DAY, "lunch", []) is None


def test_first_matching_record_wins() -> None:
    closures = [
        Closure(A_DAY, period_id=None, reason="first"),
        Closure(A_DAY, period_id=None, reason="second"),
    ]
    found = whole_day_closure(A_DAY, closures)
    assert found is not None and found.reason == "first"
