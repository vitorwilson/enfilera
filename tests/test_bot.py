"""Tests for the Telegram application bootstrap."""

from __future__ import annotations

import pytest

from enfilera.bot import build_application
from enfilera.bot_config import BotConfig, build_bot_config


def _config(**overrides: object) -> BotConfig:
    base: dict[str, object] = {
        "token_env": "ENFILERA_TOKEN",
        "admin_ids": [1],
        "issues_url": "https://example.test/issues",
        "author_url": "https://example.test/me",
        "flood_max_events": 5,
        "flood_window_seconds": 10,
    }
    base.update(overrides)
    return build_bot_config({"bot": base})


def test_build_application_uses_token_from_env() -> None:
    app = build_application(_config(), {"ENFILERA_TOKEN": "123:abc"})
    assert app.bot.token == "123:abc"


def test_build_application_raises_when_token_unset() -> None:
    with pytest.raises(ValueError, match="unset or empty"):
        build_application(_config(), {})


def test_build_application_reads_the_configured_env_var() -> None:
    config = _config(token_env="OTHER_VAR")
    app = build_application(config, {"OTHER_VAR": "999:zzz"})
    assert app.bot.token == "999:zzz"


@pytest.mark.filterwarnings("ignore:No `JobQueue` set up")
def test_build_application_has_no_job_queue() -> None:
    # Pruning is scheduled outside the bot; we deliberately skip PTB's
    # JobQueue (and its APScheduler dependency) at bootstrap. Reading the
    # absent queue is what makes PTB warn, hence the scoped filter above.
    app = build_application(_config(), {"ENFILERA_TOKEN": "123:abc"})
    assert app.job_queue is None
