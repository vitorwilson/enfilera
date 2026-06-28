"""Smoke test: the package imports and exposes a version.

Keeps CI green from the very first commit so every later change is gated by a
passing build (the project conventions: each commit passes CI and is independently
deployable).
"""

import enfilera


def test_version_is_exposed() -> None:
    assert enfilera.__version__ == "0.1.0"
