"""Tests for the operator-facing admin message builders (pure text)."""

from __future__ import annotations

from datetime import date, time

from enfilera.admin_commands import ClosureSpec, RevokeSpec
from enfilera.admin_messages import (
    NO_CLOSURES,
    admin_status,
    closure_declared,
    closure_revoked,
    closures_list,
    user_metrics,
)
from enfilera.closures import Closure
from enfilera.openness import ClosedReason, ClosedStatus, OpenStatus
from enfilera.schedule import Block

DAY = date(2026, 7, 1)


# --- closure_declared ----------------------------------------------------


def test_declared_single_day_shows_scope_and_reason() -> None:
    spec = ClosureSpec(DAY, DAY, None, "feriado")
    message = closure_declared(1, spec)
    assert "2026-07-01" in message
    assert "dia todo" in message
    assert "feriado" in message
    assert "dias" not in message  # no count for a single day


def test_declared_period_names_the_period() -> None:
    spec = ClosureSpec(DAY, DAY, "lunch", None)
    assert "período lunch" in closure_declared(1, spec)


def test_declared_range_shows_span_and_day_count() -> None:
    spec = ClosureSpec(DAY, date(2026, 7, 3), None, "recesso")
    message = closure_declared(3, spec)
    assert "2026-07-01..2026-07-03" in message
    assert "3 dias" in message


# --- closure_revoked -----------------------------------------------------


def test_revoked_found_confirms_removal() -> None:
    message = closure_revoked(RevokeSpec(DAY, "dinner"), removed=True)
    assert "removido" in message
    assert "período dinner" in message


def test_revoked_missing_says_nothing_found() -> None:
    message = closure_revoked(RevokeSpec(DAY, None), removed=False)
    assert "Nenhum fechamento encontrado" in message


# --- closures_list -------------------------------------------------------


def test_empty_list_is_the_none_note() -> None:
    assert closures_list([]) == NO_CLOSURES


def test_list_renders_one_line_per_closure() -> None:
    closures = [
        Closure(DAY, None, "feriado"),
        Closure(date(2026, 7, 2), "lunch", None),
    ]
    message = closures_list(closures)
    assert "2026-07-01 (dia todo) — feriado" in message
    assert "2026-07-02 (período lunch)" in message
    assert message.count("•") == 2


# --- admin_status --------------------------------------------------------


def test_status_open_names_period_and_block() -> None:
    status = OpenStatus("lunch", Block(time(11, 0)))
    message = admin_status(status)
    assert "Aberto" in message
    assert "lunch" in message
    assert "11:00" in message


def test_status_halted() -> None:
    assert "Pausado" in admin_status(ClosedStatus(ClosedReason.HALTED))


def test_status_closure_shows_reason() -> None:
    status = ClosedStatus(ClosedReason.CLOSURE, "ponto facultativo")
    assert "ponto facultativo" in admin_status(status)


def test_status_closure_without_reason_has_fallback() -> None:
    status = ClosedStatus(ClosedReason.CLOSURE, None)
    assert "fechamento declarado" in admin_status(status)


def test_status_outside_periods() -> None:
    message = admin_status(ClosedStatus(ClosedReason.OUTSIDE_PERIODS))
    assert "fora do horário" in message


# --- user_metrics --------------------------------------------------------


def test_user_metrics_shows_today_and_window_totals() -> None:
    message = user_metrics(3, 30, 27, [])
    assert "• Hoje: 3" in message
    assert "• Últimos 30 dias: 27" in message


def test_user_metrics_lists_each_line_under_the_window() -> None:
    message = user_metrics(3, 30, 27, [("Cartão", 15), ("Pix", 12)])
    assert "Por fila (30 dias):" in message
    assert "• Cartão: 15" in message
    assert "• Pix: 12" in message


def test_user_metrics_omits_breakdown_when_empty() -> None:
    assert "Por fila" not in user_metrics(0, 30, 0, [])
