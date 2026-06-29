"""The set of queues (lines) a cafeteria has, from config.

Each line has a stable ``id`` (used as the sample bucket key and stored as the
user's selection) and a human ``label`` shown in Telegram. Lines are
installation-specific, so they live entirely in config — a forker edits the
``[[lines]]`` list and nothing else changes (docs/PLAN.md §1).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Line:
    """One queue: stable ``id`` for storage, ``label`` for display."""

    id: str
    label: str


def build_lines(raw: dict) -> tuple[Line, ...]:
    """Parse and validate the ``[[lines]]`` config list.

    >>> build_lines({"lines": [{"id": "pix", "label": "Pix"}]})[0].label
    'Pix'
    """
    items = raw.get("lines")
    if not isinstance(items, Iterable) or isinstance(items, (str, bytes)):
        raise ValueError(f"config must define a [[lines]] list, got {items!r}")
    lines = tuple(_parse_line(item) for item in items)
    if not lines:
        raise ValueError("config must define at least one line")
    _reject_duplicate_ids(lines)
    return lines


def find_line(lines: Iterable[Line], line_id: str) -> Line | None:
    """The line with ``line_id``, or ``None`` if no line has that id."""
    for line in lines:
        if line.id == line_id:
            return line
    return None


def _parse_line(item: object) -> Line:
    if not isinstance(item, dict) or "id" not in item or "label" not in item:
        raise ValueError(f"each line needs an id and a label, got {item!r}")
    return Line(id=str(item["id"]), label=str(item["label"]))


def _reject_duplicate_ids(lines: tuple[Line, ...]) -> None:
    seen: set[str] = set()
    for line in lines:
        if line.id in seen:
            raise ValueError(f"duplicate line id {line.id!r}")
        seen.add(line.id)
