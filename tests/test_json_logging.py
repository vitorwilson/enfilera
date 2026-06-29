"""Tests for the structured JSON log formatter and root configuration."""

from __future__ import annotations

import json
import logging
import sys

from enfilera.json_logging import JSONFormatter, configure_logging


def _record(**overrides: object) -> logging.LogRecord:
    fields: dict[str, object] = {
        "name": "enfilera.bot",
        "levelname": "INFO",
        "msg": "started",
    }
    fields.update(overrides)
    return logging.makeLogRecord(fields)


def test_format_emits_core_fields() -> None:
    payload = json.loads(JSONFormatter().format(_record()))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "enfilera.bot"
    assert payload["message"] == "started"
    assert "timestamp" in payload


def test_format_is_single_line() -> None:
    assert "\n" not in JSONFormatter().format(_record(msg="line\ntwo"))


def test_format_renders_message_args() -> None:
    payload = json.loads(JSONFormatter().format(_record(msg="got %d", args=(5,))))
    assert payload["message"] == "got 5"


def test_format_merges_extra_fields() -> None:
    payload = json.loads(JSONFormatter().format(_record(user_id=42, line_id="pix")))
    assert payload["user_id"] == 42
    assert payload["line_id"] == "pix"


def test_non_serializable_extra_falls_back_to_str() -> None:
    payload = json.loads(JSONFormatter().format(_record(obj=object())))
    assert isinstance(payload["obj"], str)


def test_format_includes_exception_text() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = _record(levelname="ERROR", msg="fail", exc_info=sys.exc_info())
    payload = json.loads(JSONFormatter().format(record))
    assert "boom" in payload["exc_info"]


def test_configure_logging_installs_json_formatter() -> None:
    configure_logging()
    root = logging.getLogger()
    assert isinstance(root.handlers[0].formatter, JSONFormatter)


def test_configure_logging_is_idempotent() -> None:
    configure_logging()
    configure_logging()
    assert len(logging.getLogger().handlers) == 1


def test_configure_logging_sets_level() -> None:
    configure_logging(logging.DEBUG)
    assert logging.getLogger().level == logging.DEBUG
