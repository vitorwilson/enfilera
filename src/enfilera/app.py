"""Composition root: wire config + stores + services + handlers into a bot.

``build_app`` assembles the dependency graph and registers every handler on a
ready ``Application`` — pure wiring, no network, so it is unit-testable.
``run`` adds the I/O: configure logging, load the config file, open the
database, build the app, and start long-polling. The two clocks are injected
(server time for the handlers, a monotonic clock for the flood limiter) so
``build_app`` stays deterministic under test.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from telegram.ext import Application

from enfilera.admin_guard import AdminGuard
from enfilera.bot import build_application
from enfilera.closure_handlers import ClosureControls
from enfilera.closures_store import ClosureStore
from enfilera.config_loader import AppConfig, load_config
from enfilera.db import connect
from enfilera.error_handler import ErrorReporter
from enfilera.estimate_service import EstimationService
from enfilera.flood_guard import FloodGuard
from enfilera.halt_flag import HaltFlag
from enfilera.halt_handlers import HaltControls
from enfilera.info_handlers import InfoLinks
from enfilera.json_logging import configure_logging
from enfilera.line_handlers import LineSelection
from enfilera.metrics_handlers import MetricsControls
from enfilera.openness_service import OpennessService
from enfilera.preferences_store import LinePreferenceStore
from enfilera.rate_limit import RateLimiter
from enfilera.samples_store import SampleStore
from enfilera.submission_recorder import SubmissionRecorder
from enfilera.submissions_store import SubmissionStore
from enfilera.timer_handlers import RegisterTimer
from enfilera.user_metrics_store import UserMetricsStore
from enfilera.wait_handlers import WaitEstimate


def build_app(
    config: AppConfig,
    conn: sqlite3.Connection,
    env: Mapping[str, str],
    now: Callable[[], datetime],
    monotonic: Callable[[], float],
) -> Application:
    """Build the Telegram application with every handler registered."""
    application = build_application(config.bot, env)
    _register_handlers(application, config, conn, now, monotonic)
    return application


def run(config_path: str | Path, env: Mapping[str, str], db_path: str) -> None:
    """Load config, open the database, and start long-polling (blocking)."""
    configure_logging()
    config = load_config(config_path)
    conn = connect(db_path)
    application = build_app(config, conn, env, _utc_now, time.monotonic)
    application.run_polling()


def _utc_now() -> datetime:
    """Server time as a timezone-aware UTC instant (never the device clock)."""
    return datetime.now(UTC)


def _register_handlers(
    application: Application,
    config: AppConfig,
    conn: sqlite3.Connection,
    now: Callable[[], datetime],
    monotonic: Callable[[], float],
) -> None:
    samples = SampleStore(conn)
    preferences = LinePreferenceStore(conn)
    closures = ClosureStore(conn)
    halt = HaltFlag(conn)
    openness = OpennessService(config.schedule, closures, halt)
    estimates = EstimationService(
        samples, config.schedule, config.estimation, config.retention_days
    )
    recorder = SubmissionRecorder(samples, SubmissionStore(conn), config.schedule)
    limiter = RateLimiter(config.bot.flood_max_events, config.bot.flood_window_seconds)
    guard = AdminGuard(config.bot.admin_ids)

    FloodGuard(limiter, monotonic).register(application)
    LineSelection(config.lines, preferences).register(application)
    WaitEstimate(config.lines, preferences, openness, estimates, now).register(
        application
    )
    RegisterTimer(
        config.lines,
        preferences,
        openness,
        recorder,
        config.geofence,
        config.estimation,
        now,
    ).register(application)
    InfoLinks(config.bot.issues_url, config.bot.author_url).register(application)
    HaltControls(guard, halt, openness, now).register(application)
    ClosureControls(guard, closures, config.schedule, now).register(application)
    MetricsControls(
        guard, UserMetricsStore(conn), config.lines, config.schedule, now
    ).register(application)
    ErrorReporter().register(application)
