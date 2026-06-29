"""Tests for the composition root (wiring config + stores into the bot)."""

from __future__ import annotations

import sqlite3
import tomllib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from telegram.ext import Application, CommandHandler, TypeHandler

from enfilera.app import build_app
from enfilera.config_loader import build_config

EXAMPLE = Path(__file__).resolve().parent.parent / "config" / "config.example.toml"
ENV = {"ENFILERA_BOT_TOKEN": "123:abc"}


def _config() -> object:
    with open(EXAMPLE, "rb") as handle:
        return build_config(tomllib.load(handle))


def _app(conn: sqlite3.Connection) -> Application:
    return build_app(_config(), conn, ENV, lambda: datetime.now(UTC), lambda: 0.0)


def _command_names(app: Application) -> set[str]:
    names: set[str] = set()
    for handlers in app.handlers.values():
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                names |= set(handler.commands)
    return names


def test_build_app_registers_every_user_command(memory_db: sqlite3.Connection) -> None:
    commands = _command_names(_app(memory_db))
    assert {"fila", "agora", "registrar", "parar", "bug", "sobre"} <= commands


def test_build_app_registers_every_admin_command(memory_db: sqlite3.Connection) -> None:
    commands = _command_names(_app(memory_db))
    assert {
        "pausar",
        "retomar",
        "status",
        "fechar",
        "fechamentos",
        "reabrir",
    } <= commands


def test_build_app_installs_flood_guard_ahead_of_handlers(
    memory_db: sqlite3.Connection,
) -> None:
    app = _app(memory_db)
    assert any(isinstance(h, TypeHandler) for h in app.handlers[-1])
    assert min(app.handlers) < 0  # the guard's group runs before group 0


def test_build_app_raises_without_a_token(memory_db: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="unset or empty"):
        build_app(_config(), memory_db, {}, lambda: datetime.now(UTC), lambda: 0.0)
