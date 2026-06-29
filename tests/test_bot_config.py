"""Tests for bot config parsing and token resolution.

The token never lives in config; only the env-var name does. Resolution reads
an injected mapping, so these tests never touch the real environment.
"""

import pytest

from enfilera.bot_config import build_bot_config, resolve_token


def _raw(**overrides: object) -> dict:
    bot = {
        "token_env": "ENFILERA_BOT_TOKEN",
        "admin_ids": [11111111, 22222222],
        "issues_url": "https://example.test/issues",
        "author_url": "https://example.test/author",
        "flood_max_events": 5,
        "flood_window_seconds": 10,
    }
    bot.update(overrides)
    return {"bot": bot}


def test_build_parses_fields() -> None:
    config = build_bot_config(_raw())
    assert config.token_env == "ENFILERA_BOT_TOKEN"
    assert config.admin_ids == frozenset({11111111, 22222222})
    assert config.flood_max_events == 5


def test_build_rejects_non_integer_admin_id() -> None:
    with pytest.raises(ValueError, match="admin id"):
        build_bot_config(_raw(admin_ids=["not-an-int"]))


def test_build_rejects_bool_admin_id() -> None:
    with pytest.raises(ValueError, match="admin id"):
        build_bot_config(_raw(admin_ids=[True]))


def test_build_rejects_non_positive_flood_window() -> None:
    with pytest.raises(ValueError, match="flood_window_seconds"):
        build_bot_config(_raw(flood_window_seconds=0))


def test_resolve_token_reads_named_env_var() -> None:
    config = build_bot_config(_raw())
    assert resolve_token(config, {"ENFILERA_BOT_TOKEN": "123:abc"}) == "123:abc"


def test_resolve_token_missing_raises_with_var_name() -> None:
    config = build_bot_config(_raw())
    with pytest.raises(ValueError, match="ENFILERA_BOT_TOKEN"):
        resolve_token(config, {})


def test_resolve_token_empty_raises() -> None:
    config = build_bot_config(_raw())
    with pytest.raises(ValueError, match="unset or empty"):
        resolve_token(config, {"ENFILERA_BOT_TOKEN": ""})
