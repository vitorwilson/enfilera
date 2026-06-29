"""Structured JSON logging for debugging / observability.

Project convention: logs are structured JSON for observability; plain text is
reserved for user-facing CLI output. Every log record becomes one JSON object
per line so the Pi's journald stream is greppable and machine-parseable.
User-facing bot replies never pass through here — they go to Telegram, not
the log.

Anything a caller attaches via ``logger.info("...", extra={"user_id": 42})``
is merged into the JSON, so call sites add context without a bespoke format.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

# Standard LogRecord attributes are rendered explicitly or dropped; only keys
# a caller adds via ``extra=`` survive into the JSON. Derive the reserved set
# from a blank record so it tracks the running Python's LogRecord shape.
_RESERVED = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JSONFormatter(logging.Formatter):
    """Render a ``LogRecord`` as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        payload.update(_extra_fields(record))
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """Install the JSON formatter as the root logger's only stream handler.

    Idempotent: replaces existing handlers so repeated calls (tests, a bot
    restart in-process) never stack duplicate output.

    >>> configure_logging(logging.DEBUG)
    >>> logging.getLogger().level == logging.DEBUG
    True
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def _extra_fields(record: logging.LogRecord) -> dict[str, object]:
    """Caller-supplied ``extra=`` keys, minus standard ``LogRecord`` attrs."""
    return {k: v for k, v in record.__dict__.items() if k not in _RESERVED}
