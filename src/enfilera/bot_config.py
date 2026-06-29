"""Bot-level config: admin allowlist, links, flood limits, and the token.

The token itself is never in the file — only the *name* of the environment
variable that holds it (docs/PLAN.md §4). ``resolve_token`` reads that variable
from an injected environment mapping (so tests pass a fake dict instead of
touching ``os.environ``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from enfilera.config_parsing import positive_int, section


@dataclass(frozen=True)
class BotConfig:
    """Static bot configuration parsed from ``[bot]``."""

    token_env: str
    admin_ids: frozenset[int]
    issues_url: str
    author_url: str
    flood_max_events: int
    flood_window_seconds: int


def build_bot_config(raw: dict) -> BotConfig:
    """Parse and validate the ``[bot]`` section.

    >>> build_bot_config({"bot": {
    ...     "token_env": "TOK", "admin_ids": [1], "issues_url": "u",
    ...     "author_url": "a", "flood_max_events": 5,
    ...     "flood_window_seconds": 10}}).token_env
    'TOK'
    """
    bot = section(raw, "bot")
    return BotConfig(
        token_env=str(bot["token_env"]),
        admin_ids=_parse_admin_ids(bot["admin_ids"]),
        issues_url=str(bot["issues_url"]),
        author_url=str(bot["author_url"]),
        flood_max_events=positive_int(bot["flood_max_events"], "flood_max_events"),
        flood_window_seconds=positive_int(
            bot["flood_window_seconds"], "flood_window_seconds"
        ),
    )


def resolve_token(config: BotConfig, env: Mapping[str, str]) -> str:
    """The bot token from ``env[config.token_env]``; raises if unset or empty.

    >>> resolve_token(
    ...     build_bot_config({"bot": {"token_env": "TOK", "admin_ids": [],
    ...         "issues_url": "u", "author_url": "a", "flood_max_events": 1,
    ...         "flood_window_seconds": 1}}),
    ...     {"TOK": "123:abc"})
    '123:abc'
    """
    token = env.get(config.token_env)
    if not token:
        raise ValueError(f"bot token env var {config.token_env!r} is unset or empty")
    return token


def _parse_admin_ids(value: object) -> frozenset[int]:
    if not isinstance(value, list):
        raise ValueError(f"admin_ids must be a list of integers, got {value!r}")
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(f"admin id must be an integer, got {item!r}")
    return frozenset(value)
