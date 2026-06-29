"""Shared validators for parsing the static TOML config.

Tiny, dependency-free helpers used by every config builder (schedule,
estimation, …) so section lookup and numeric validation live in one place
instead of being re-implemented per section. Each raiser names the offending
value and the expected shape, per the project conventions.
"""

from __future__ import annotations

from collections.abc import Mapping


def section(raw: Mapping[str, object], name: str) -> Mapping[str, object]:
    """The ``[name]`` table from a parsed config mapping.

    >>> section({"estimation": {"min_samples": 3}}, "estimation")["min_samples"]
    3
    """
    table = raw.get(name)
    if not isinstance(table, Mapping):
        raise ValueError(f"config section [{name}] is missing, got {table!r}")
    return table


def positive_int(value: object, field: str) -> int:
    """A strictly-positive ``int``, rejecting ``bool`` (since ``True == 1``).

    >>> positive_int(3, "min_samples")
    3
    """
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field} must be a positive integer, got {value!r}")
    return value


def positive_number(value: object, field: str) -> float:
    """A strictly-positive real (``int`` or ``float``), rejecting ``bool``.

    >>> positive_number(3.0, "mad_k")
    3.0
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{field} must be a positive number, got {value!r}")
    return float(value)
