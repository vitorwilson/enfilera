"""Closure records and pure active-lookups.

One record type covers every kind of closure (feriado, ponto facultativo,
ad-hoc "not opening today"): a single ``date`` plus an optional ``period_id``
(``None`` = the whole day) and an optional ``reason`` label. Date ranges are
expanded to one record per day at the persistence layer so this lookup stays
trivial. No I/O here — ``closures`` is injected by the caller.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Closure:
    """A declared closure for one day; whole-day when ``period_id`` is None."""

    date: date
    period_id: str | None = None
    reason: str | None = None


def whole_day_closure(on: date, closures: Iterable[Closure]) -> Closure | None:
    """The whole-day closure for ``on`` (``period_id is None``), else None."""
    for closure in closures:
        if closure.date == on and closure.period_id is None:
            return closure
    return None


def period_closure(
    on: date, period_id: str, closures: Iterable[Closure]
) -> Closure | None:
    """The closure shutting exactly ``period_id`` on ``on``, else None.

    Period-specific only: a whole-day record (``period_id is None``) is *not*
    matched here — that case is handled by ``whole_day_closure``.
    """
    for closure in closures:
        if closure.date == on and closure.period_id == period_id:
            return closure
    return None
