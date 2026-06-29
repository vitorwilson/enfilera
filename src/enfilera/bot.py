"""Bootstrap the Telegram application from parsed config.

The single thin seam over ``python-telegram-bot``: ``build_application`` turns
a ``BotConfig`` plus the process environment into a ready ``Application``,
resolving the bot token from the env var named in config (never the committed
file). Handlers are registered elsewhere — this module only constructs and
wires the application object, so the rest of the bot never imports
``ApplicationBuilder`` directly.

We disable PTB's ``JobQueue`` deliberately: the only scheduled work (sample
pruning) runs outside the bot, so we avoid pulling in the APScheduler extra.
"""

from __future__ import annotations

from collections.abc import Mapping

from telegram.ext import Application, ApplicationBuilder

from enfilera.bot_config import BotConfig, resolve_token


def build_application(config: BotConfig, env: Mapping[str, str]) -> Application:
    """Construct the Telegram ``Application`` with the token from ``env``.

    The token is read from the env var named by ``config.token_env``; a
    missing or empty value raises before any network call (``resolve_token``).
    Building is offline — it constructs objects but opens no connection.

    >>> from enfilera.bot_config import build_bot_config
    >>> cfg = build_bot_config({"bot": {"token_env": "TOK", "admin_ids": [],
    ...     "issues_url": "u", "author_url": "a", "flood_max_events": 1,
    ...     "flood_window_seconds": 1}})
    >>> build_application(cfg, {"TOK": "123:abc"}).bot.token
    '123:abc'
    """
    token = resolve_token(config, env)
    return ApplicationBuilder().token(token).job_queue(None).build()
