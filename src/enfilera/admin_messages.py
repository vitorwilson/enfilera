"""Operator-facing message text for the admin commands (plain text, pt-BR).

Pure builders, kept apart from the Telegram glue so the wording is tested in
isolation and lives in one place. These are for the allowlisted operator, not
end users, but the same rule holds: plain text out, JSON only in the logs.
The closure list and status reflect the *raw* period ids from config so the
surface stays forkable — a fork's own ids show through unchanged.
"""

from __future__ import annotations

from datetime import date

from enfilera.admin_commands import ClosureSpec, RevokeSpec
from enfilera.closures import Closure
from enfilera.openness import ClosedReason, OpenStatus, Status

HALTED = "Bot pausado. Nenhum cronômetro será aceito até você usar /retomar."
RESUMED = "Bot retomado. Operação normal."
NO_CLOSURES = "Nenhum fechamento futuro."

_CLOSED_TEXT = {
    ClosedReason.HALTED: "Pausado pelo operador. Use /retomar para voltar.",
    ClosedReason.NON_OPERATING_DAY: "Fechado hoje — dia sem operação.",
    ClosedReason.OUTSIDE_PERIODS: "Fechado — fora do horário de funcionamento.",
}


def user_metrics(
    today: int, window_days: int, window_count: int, per_line: list[tuple[str, int]]
) -> str:
    """Render the ``/usuarios`` read: active users plus a per-line split.

    ``per_line`` is ``(label, count)`` in config order; an empty list omits
    the breakdown. ``window_days`` labels the rolling window so the wording
    and the query never drift apart.

    >>> user_metrics(3, 30, 27, [("Cartão", 15), ("Pix", 12)]).splitlines()[1]
    '• Hoje: 3'
    """
    lines = [
        "Usuários únicos:",
        f"• Hoje: {today}",
        f"• Últimos {window_days} dias: {window_count}",
    ]
    if per_line:
        lines += ["", f"Por fila ({window_days} dias):"]
        lines += [f"• {label}: {count}" for label, count in per_line]
    return "\n".join(lines)


def closure_declared(count: int, spec: ClosureSpec) -> str:
    """Confirm a declared closure, noting the day count for a range.

    >>> from datetime import date
    >>> closure_declared(1, ClosureSpec(date(2026, 7, 1), date(2026, 7, 1),
    ...                                 None, "feriado"))
    'Fechamento declarado: 2026-07-01 (dia todo) — feriado.'
    """
    scope = _scope(spec.period_id)
    label = f"Fechamento declarado: {_span(spec.start, spec.end)} ({scope})"
    if spec.reason:
        label += f" — {spec.reason}"
    if count > 1:
        label += f" ({count} dias)"
    return label + "."


def closure_revoked(spec: RevokeSpec, removed: bool) -> str:
    """Confirm a revoke, or report that no such closure existed."""
    where = f"{spec.date.isoformat()} ({_scope(spec.period_id)})"
    if removed:
        return f"Fechamento removido: {where}."
    return f"Nenhum fechamento encontrado para {where}."


def closures_list(closures: list[Closure]) -> str:
    """The upcoming-closures listing, or a note that there are none."""
    if not closures:
        return NO_CLOSURES
    lines = ["Próximos fechamentos:"]
    lines.extend(_closure_line(closure) for closure in closures)
    return "\n".join(lines)


def admin_status(status: Status) -> str:
    """The current open/closed/halt state and why, for ``/status``."""
    if isinstance(status, OpenStatus):
        return (
            f"Aberto agora — período {status.period_id}, "
            f"bloco {status.block.start:%H:%M}."
        )
    if status.reason is ClosedReason.CLOSURE:
        return f"Fechado — {status.detail or 'fechamento declarado'}."
    return _CLOSED_TEXT[status.reason]


def _closure_line(closure: Closure) -> str:
    line = f"• {closure.date.isoformat()} ({_scope(closure.period_id)})"
    if closure.reason:
        line += f" — {closure.reason}"
    return line


def _span(start: date, end: date) -> str:
    if start == end:
        return start.isoformat()
    return f"{start.isoformat()}..{end.isoformat()}"


def _scope(period_id: str | None) -> str:
    return "dia todo" if period_id is None else f"período {period_id}"
