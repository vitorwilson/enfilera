"""User-facing message text shared across handlers (plain text, pt-BR).

Centralizes the strings and builders that more than one handler shows, so the
wording stays consistent in one place. User-facing output is plain text, never
JSON — structured JSON is only for the observability logs.
"""

from __future__ import annotations

from enfilera.openness import ClosedStatus

NO_LINE = "Escolha sua fila primeiro com /fila."


def closed_message(status: ClosedStatus) -> str:
    """Closed notice, naming the closure reason when one was declared.

    >>> from enfilera.openness import ClosedReason
    >>> closed_message(ClosedStatus(ClosedReason.CLOSURE, "feriado"))
    'Fechado agora: feriado.'
    """
    if status.detail:
        return f"Fechado agora: {status.detail}."
    return "Fechado agora. Volte no horário de funcionamento."
