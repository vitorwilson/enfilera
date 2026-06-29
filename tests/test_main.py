"""Tests for the ``python -m enfilera`` entry point."""

from __future__ import annotations

import pytest

from enfilera import __main__, app


def test_main_passes_overridden_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        app,
        "run",
        lambda config_path, env, db_path: captured.update(
            config_path=config_path, db_path=db_path
        ),
    )
    monkeypatch.setenv("ENFILERA_CONFIG", "/etc/enfilera/config.toml")
    monkeypatch.setenv("ENFILERA_DB", "/var/lib/enfilera.db")
    __main__.main()
    assert captured["config_path"] == "/etc/enfilera/config.toml"
    assert captured["db_path"] == "/var/lib/enfilera.db"


def test_main_falls_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        app,
        "run",
        lambda config_path, env, db_path: captured.update(
            config_path=config_path, db_path=db_path
        ),
    )
    monkeypatch.delenv("ENFILERA_CONFIG", raising=False)
    monkeypatch.delenv("ENFILERA_DB", raising=False)
    __main__.main()
    assert captured["config_path"] == "config/config.toml"
    assert captured["db_path"] == "enfilera.db"
