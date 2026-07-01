"""Operator commands for declaring, listing, and revoking closures.

``/fechar`` declares a closure (today, a future date, or a range; whole day or
one period; optional reason), ``/fechamentos`` lists the upcoming ones, and
``/reabrir`` removes a specific one — revoke is first-class so a stale closure
can never silently keep the bot dark (docs/PLAN.md §4). All three sit behind
the admin guard. Argument parsing is a pure function; persistence is the
closure store; this handler only owns the clock (for "today") and the wiring.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from enfilera.admin_commands import parse_closure_args, parse_revoke_args
from enfilera.admin_guard import AdminGuard, admin_only
from enfilera.admin_messages import closure_declared, closure_revoked, closures_list
from enfilera.closures_store import ClosureStore
from enfilera.schedule import Schedule, local_date

CLOSE_COMMAND = "fechar"
LIST_COMMAND = "fechamentos"
REOPEN_COMMAND = "reabrir"

_logger = logging.getLogger(__name__)


class ClosureControls:
    """Wires /fechar, /fechamentos, and /reabrir to the closure store."""

    def __init__(
        self,
        guard: AdminGuard,
        closures: ClosureStore,
        schedule: Schedule,
        clock: Callable[[], datetime],
    ) -> None:
        self._guard = guard
        self._closures = closures
        self._schedule = schedule
        self._clock = clock
        self._period_ids = frozenset(period.id for period in schedule.periods)

    def register(self, application: Application) -> None:
        """Add the /fechar, /fechamentos, and /reabrir command handlers."""
        application.add_handler(CommandHandler(CLOSE_COMMAND, self.declare))
        application.add_handler(CommandHandler(LIST_COMMAND, self.list_upcoming))
        application.add_handler(CommandHandler(REOPEN_COMMAND, self.revoke))

    @admin_only
    async def declare(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """``/fechar`` — declare a closure for a day, period, or range."""
        try:
            spec = parse_closure_args(context.args, self._today(), self._period_ids)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        count = self._closures.declare_range(
            spec.start, spec.end, spec.period_id, spec.reason
        )
        _logger.info(
            "closure declared",
            extra={
                "user_id": update.effective_user.id,
                "start": spec.start.isoformat(),
                "end": spec.end.isoformat(),
                "period_id": spec.period_id,
                "days": count,
            },
        )
        await update.effective_message.reply_text(closure_declared(count, spec))

    @admin_only
    async def list_upcoming(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """``/fechamentos`` — list upcoming closures, today onward."""
        upcoming = self._closures.upcoming(self._today())
        await update.effective_message.reply_text(closures_list(upcoming))

    @admin_only
    async def revoke(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """``/reabrir`` — remove a specific closure (whole day or one period)."""
        try:
            spec = parse_revoke_args(context.args, self._today(), self._period_ids)
        except ValueError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        removed = self._closures.revoke(spec.date, spec.period_id)
        _logger.info(
            "closure revoked",
            extra={
                "user_id": update.effective_user.id,
                "date": spec.date.isoformat(),
                "period_id": spec.period_id,
                "removed": removed,
            },
        )
        await update.effective_message.reply_text(closure_revoked(spec, removed))

    def _today(self) -> date:
        """Server time localized to the cafeteria zone, as a calendar date."""
        return local_date(self._clock(), self._schedule)
