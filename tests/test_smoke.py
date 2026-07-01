"""Smoke test: the package imports and exposes a well-formed version.

Keeps CI green from the very first commit so every later change is gated by a
passing build (the project conventions: each commit passes CI and is
independently deployable). Asserts the version is *present and semver-shaped*
rather than pinning a literal, so cutting a release doesn't require editing a
test — the version's single source of truth stays ``enfilera.__version__``.
"""

import re

import enfilera


def test_version_is_exposed() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", enfilera.__version__), enfilera.__version__
