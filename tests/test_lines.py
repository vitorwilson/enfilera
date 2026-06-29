"""Tests for parsing the configured lines."""

import pytest

from enfilera.lines import Line, build_lines, find_line

LINES = (Line("card", "Cartão"), Line("pix", "Pix"))


def _raw(items: object) -> dict:
    return {"lines": items}


def test_build_lines_parses_id_and_label() -> None:
    lines = build_lines(_raw([{"id": "card", "label": "Cartão"}]))
    assert lines == (Line("card", "Cartão"),)


def test_build_lines_rejects_missing_list() -> None:
    with pytest.raises(ValueError, match=r"\[\[lines\]\]"):
        build_lines({})


def test_build_lines_rejects_empty_list() -> None:
    with pytest.raises(ValueError, match="at least one line"):
        build_lines(_raw([]))


def test_build_lines_rejects_duplicate_ids() -> None:
    items = [{"id": "pix", "label": "A"}, {"id": "pix", "label": "B"}]
    with pytest.raises(ValueError, match="pix"):
        build_lines(_raw(items))


def test_build_lines_rejects_item_without_label() -> None:
    with pytest.raises(ValueError, match="id and a label"):
        build_lines(_raw([{"id": "card"}]))


def test_find_line_returns_match() -> None:
    assert find_line(LINES, "pix") == Line("pix", "Pix")


def test_find_line_missing_is_none() -> None:
    assert find_line(LINES, "ghost") is None
