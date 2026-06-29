"""Pure parsing of admin closure-command arguments into intents.

No Telegram, no DB, no clock: these functions turn the raw ``context.args``
token list of ``/fechar`` and ``/reabrir`` into validated value objects the
handlers act on. ``today`` and the set of known ``period_ids`` are injected so
the parser stays a pure function of its inputs (the handler owns the clock and
the config). A malformed argument raises ``ValueError`` naming the offending
token and the expected shape, which the handler relays to the operator.

Date tokens accept ``hoje`` (today), an ISO ``AAAA-MM-DD`` date, or — for
``/fechar`` only — a ``start..end`` inclusive range. For ``/fechar`` a second
token is read as the period **only** when it matches a configured period id;
otherwise everything after the date is the free-text reason. ``/reabrir``
targets exactly one slot, so its optional second token must be a known period.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

_TODAY_TOKEN = "hoje"
_RANGE_SEP = ".."
# A closure range stores one row per day; cap the span so a typo like
# `2026-01-01..2099-01-01` can't write tens of thousands of rows. ~1 year is
# far beyond any real cafeteria closure.
_MAX_RANGE_DAYS = 366
_CLOSE_USAGE = (
    "uso: /fechar <hoje|AAAA-MM-DD|AAAA-MM-DD..AAAA-MM-DD> [período] [motivo]"
)
_REOPEN_USAGE = "uso: /reabrir <hoje|AAAA-MM-DD> [período]"


@dataclass(frozen=True)
class ClosureSpec:
    """A closure to declare: an inclusive date span, optional period + reason."""

    start: date
    end: date
    period_id: str | None
    reason: str | None


@dataclass(frozen=True)
class RevokeSpec:
    """A single closure slot to remove: one date and an optional period."""

    date: date
    period_id: str | None


def parse_closure_args(
    args: list[str], today: date, period_ids: frozenset[str]
) -> ClosureSpec:
    """Parse ``/fechar`` arguments into a :class:`ClosureSpec`.

    >>> parse_closure_args(["hoje", "lunch", "sem", "água"],
    ...                    date(2026, 6, 29), frozenset({"lunch"})).reason
    'sem água'
    """
    if not args:
        raise ValueError(_CLOSE_USAGE)
    start, end = _parse_date_spec(args[0], today)
    period_id, reason = _split_period_reason(args[1:], period_ids)
    return ClosureSpec(start=start, end=end, period_id=period_id, reason=reason)


def parse_revoke_args(
    args: list[str], today: date, period_ids: frozenset[str]
) -> RevokeSpec:
    """Parse ``/reabrir`` arguments into a :class:`RevokeSpec`.

    >>> parse_revoke_args(["2026-07-01"], date(2026, 6, 29), frozenset())
    RevokeSpec(date=datetime.date(2026, 7, 1), period_id=None)
    """
    if not args:
        raise ValueError(_REOPEN_USAGE)
    on = _parse_one_date(args[0], today)
    period_id = _required_period(args[1:], period_ids)
    return RevokeSpec(date=on, period_id=period_id)


def _parse_date_spec(token: str, today: date) -> tuple[date, date]:
    if _RANGE_SEP not in token:
        single = _parse_one_date(token, today)
        return single, single
    start_token, _, end_token = token.partition(_RANGE_SEP)
    start = _parse_one_date(start_token, today)
    end = _parse_one_date(end_token, today)
    if end < start:
        raise ValueError(f"intervalo inválido: fim {end} antes do início {start}")
    span = (end - start).days
    if span > _MAX_RANGE_DAYS:
        raise ValueError(
            f"intervalo longo demais: {span} dias entre {start} e {end} "
            f"(máx {_MAX_RANGE_DAYS}); verifique as datas"
        )
    return start, end


def _parse_one_date(token: str, today: date) -> date:
    if token == _TODAY_TOKEN:
        return today
    try:
        return date.fromisoformat(token)
    except ValueError as exc:
        raise ValueError(f"data inválida {token!r}; use 'hoje' ou AAAA-MM-DD") from exc


def _split_period_reason(
    rest: list[str], period_ids: frozenset[str]
) -> tuple[str | None, str | None]:
    if rest and rest[0] in period_ids:
        return rest[0], _join_reason(rest[1:])
    return None, _join_reason(rest)


def _required_period(rest: list[str], period_ids: frozenset[str]) -> str | None:
    if not rest:
        return None
    token = rest[0]
    if token not in period_ids:
        raise ValueError(
            f"período desconhecido {token!r}; conhecidos: {sorted(period_ids)}"
        )
    return token


def _join_reason(tokens: list[str]) -> str | None:
    return " ".join(tokens) if tokens else None
