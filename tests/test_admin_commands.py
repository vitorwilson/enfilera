"""Tests for parsing admin closure-command arguments.

Pure parsing: no Telegram, no DB. Covers the date forms (today / ISO / range),
the period-vs-reason split for /fechar, the strict period for /reabrir, and the
error messages a malformed argument must surface to the operator.
"""

from __future__ import annotations

from datetime import date

import pytest

from enfilera.admin_commands import (
    ClosureSpec,
    RevokeSpec,
    parse_closure_args,
    parse_revoke_args,
)

TODAY = date(2026, 6, 29)
PERIODS = frozenset({"lunch", "dinner"})


# --- /fechar -------------------------------------------------------------


def test_today_keyword_resolves_to_injected_today() -> None:
    spec = parse_closure_args(["hoje"], TODAY, PERIODS)
    assert spec == ClosureSpec(TODAY, TODAY, None, None)


def test_iso_date_whole_day_no_reason() -> None:
    spec = parse_closure_args(["2026-07-01"], TODAY, PERIODS)
    assert spec == ClosureSpec(date(2026, 7, 1), date(2026, 7, 1), None, None)


def test_period_token_recognised_and_reason_follows() -> None:
    spec = parse_closure_args(["2026-07-01", "lunch", "sem", "água"], TODAY, PERIODS)
    assert spec == ClosureSpec(date(2026, 7, 1), date(2026, 7, 1), "lunch", "sem água")


def test_unknown_second_token_becomes_part_of_the_reason() -> None:
    # A non-period first reason word means a WHOLE-day closure, reason kept whole.
    spec = parse_closure_args(["hoje", "ponto", "facultativo"], TODAY, PERIODS)
    assert spec == ClosureSpec(TODAY, TODAY, None, "ponto facultativo")


def test_range_expands_to_inclusive_start_and_end() -> None:
    spec = parse_closure_args(["2026-07-01..2026-07-03", "recesso"], TODAY, PERIODS)
    assert spec == ClosureSpec(date(2026, 7, 1), date(2026, 7, 3), None, "recesso")


def test_range_with_period_applies_to_every_day() -> None:
    spec = parse_closure_args(["2026-07-01..2026-07-02", "dinner"], TODAY, PERIODS)
    assert spec == ClosureSpec(date(2026, 7, 1), date(2026, 7, 2), "dinner", None)


def test_empty_args_raise_usage() -> None:
    with pytest.raises(ValueError, match="uso: /fechar"):
        parse_closure_args([], TODAY, PERIODS)


def test_bad_date_names_the_offending_token() -> None:
    with pytest.raises(ValueError, match="data inválida 'amanhã'"):
        parse_closure_args(["amanhã"], TODAY, PERIODS)


def test_reversed_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="intervalo inválido"):
        parse_closure_args(["2026-07-03..2026-07-01"], TODAY, PERIODS)


def test_absurdly_long_range_is_rejected() -> None:
    # A typo spanning years would write tens of thousands of rows; cap it.
    with pytest.raises(ValueError, match="longo demais"):
        parse_closure_args(["2026-01-01..2099-01-01"], TODAY, PERIODS)


def test_range_at_the_span_limit_is_accepted() -> None:
    # 366-day span (367 inclusive days) is the boundary and must still parse.
    spec = parse_closure_args(["2026-01-01..2027-01-02"], TODAY, PERIODS)
    assert (spec.end - spec.start).days == 366


# --- /reabrir ------------------------------------------------------------


def test_revoke_whole_day_default() -> None:
    spec = parse_revoke_args(["2026-07-01"], TODAY, PERIODS)
    assert spec == RevokeSpec(date(2026, 7, 1), None)


def test_revoke_specific_period() -> None:
    spec = parse_revoke_args(["hoje", "lunch"], TODAY, PERIODS)
    assert spec == RevokeSpec(TODAY, "lunch")


def test_revoke_rejects_unknown_period() -> None:
    with pytest.raises(ValueError, match="período desconhecido 'brunch'"):
        parse_revoke_args(["hoje", "brunch"], TODAY, PERIODS)


def test_revoke_empty_args_raise_usage() -> None:
    with pytest.raises(ValueError, match="uso: /reabrir"):
        parse_revoke_args([], TODAY, PERIODS)


def test_revoke_does_not_accept_a_range() -> None:
    with pytest.raises(ValueError, match="data inválida"):
        parse_revoke_args(["2026-07-01..2026-07-02"], TODAY, PERIODS)
