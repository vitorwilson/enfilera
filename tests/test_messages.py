"""Tests for shared user-facing message builders."""

from __future__ import annotations

from enfilera.messages import closed_message
from enfilera.openness import ClosedReason, ClosedStatus


def test_closed_message_names_the_closure_reason() -> None:
    status = ClosedStatus(ClosedReason.CLOSURE, "feriado")
    assert closed_message(status) == "Fechado agora: feriado."


def test_closed_message_without_detail_is_generic() -> None:
    status = ClosedStatus(ClosedReason.OUTSIDE_PERIODS)
    assert "Fechado" in closed_message(status)
    assert ":" not in closed_message(status)
