"""Operator command for user-activity metrics (``/usuarios``).

Reports distinct *active* users — today and over a rolling window — plus a
per-line breakdown, all read from the submissions table via the metrics
store. Behind the admin guard; this handler owns the clock (to fix "today"
and the window in the cafeteria's timezone) and maps line ids to their config
labels for display. The counting and the wording live elsewhere so this stays
thin (docs/PLAN.md §4).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from enfilera.admin_guard import AdminGuard, admin_only
from enfilera.admin_messages import user_metrics
from enfilera.lines import Line
from enfilera.schedule import Schedule, local_date
from enfilera.user_metrics_store import UserMetricsStore

USERS_COMMAND = "usuarios"
# Rolling window for the "active users" headline. Matches the sample-retention
# default so the figure reflects roughly the data the estimator still holds.
_WINDOW_DAYS = 30
# Bucket for rows whose line id is unknown — pre-migration NULLs or a line a
# forker has since removed — so the per-line split still reconciles with the
# headline instead of silently dropping those users.
_UNKNOWN_LABEL = "desconhecida"


class MetricsControls:
    """Wires /usuarios to the read-only user-metrics store."""

    def __init__(
        self,
        guard: AdminGuard,
        metrics: UserMetricsStore,
        lines: tuple[Line, ...],
        schedule: Schedule,
        clock: Callable[[], datetime],
    ) -> None:
        self._guard = guard
        self._metrics = metrics
        self._lines = lines
        self._schedule = schedule
        self._clock = clock

    def register(self, application: Application) -> None:
        """Add the /usuarios command handler."""
        application.add_handler(CommandHandler(USERS_COMMAND, self.report))

    @admin_only
    async def report(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """``/usuarios`` — distinct active users, today and over the window."""
        today = local_date(self._clock(), self._schedule)
        cutoff = today - timedelta(days=_WINDOW_DAYS - 1)
        message = user_metrics(
            self._metrics.active_on(today),
            _WINDOW_DAYS,
            self._metrics.active_since(cutoff),
            self._labelled_counts(self._metrics.per_line_since(cutoff)),
        )
        await update.effective_message.reply_text(message)

    def _labelled_counts(self, counts: dict[str | None, int]) -> list[tuple[str, int]]:
        """Config-ordered ``(label, count)``, with unknown/stale ids folded last.

        Showing every configured line (0 included) keeps the surface forkable;
        the trailing "desconhecida" entry makes the split reconcile with the
        headline even for rows written before the line column existed.
        """
        remaining = dict(counts)
        labelled = [(line.label, remaining.pop(line.id, 0)) for line in self._lines]
        unknown = sum(remaining.values())
        if unknown:
            labelled.append((_UNKNOWN_LABEL, unknown))
        return labelled
