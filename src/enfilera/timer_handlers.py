"""Telegram handler for the register-time timer (/registrar → location → /parar).

The flow that turns a student's queue wait into a sample:

1. ``/registrar`` gates on a chosen line, the cafeteria being open, and the
   one-per-period rule, then asks for the user's live location.
2. The location message is a *presence check* only: if it is within the
   geofence the timer starts (queue-join instant); the coordinates are read
   for the radius test and then dropped — never stored (docs/PLAN.md §3).
3. ``/parar`` measures the elapsed transit from two server timestamps and shows
   it with a confirm / resume choice. Confirm applies the physical clamp and
   records the sample; resume keeps the *original* timer running. This guards a
   premature stop: a plausible-but-early value (10 min when it was 20) passes
   the clamp, so the user must confirm it is the real turnstile moment.

Per-user flow state (start instant, line, pending elapsed) lives in
``context.user_data``; all gating is in injected services, so this handler
stays an orchestrator.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from enfilera.estimate import format_estimate
from enfilera.estimation_config import SECONDS_PER_MINUTE, EstimationConfig
from enfilera.geofence import Geofence, within_radius
from enfilera.lines import Line
from enfilera.messages import NO_LINE, closed_message
from enfilera.openness_service import OpennessService
from enfilera.preferences_store import LinePreferenceStore, chosen_line
from enfilera.submission_recorder import SubmissionRecorder
from enfilera.timer import ElapsedVerdict, classify_elapsed, elapsed_seconds

START_COMMAND = "registrar"
STOP_COMMAND = "parar"
DECISION_PATTERN = r"^timer:"
_CONFIRM = "timer:confirm"
_RESUME = "timer:resume"

_START_PROMPT = (
    "Compartilhe sua localização para começar o cronômetro.\n\n"
    "🔒 Ela serve só para confirmar que você está no restaurante e é "
    "descartada logo em seguida — o bot nunca guarda sua localização."
)
_OUTSIDE = "Você precisa estar no restaurante para começar."
_ALREADY = "Você já registrou um tempo neste período. Volte no próximo."
_NEED_START = "Use /registrar para começar antes de enviar a localização."
_STARTED = "Cronômetro iniciado! Toque em /parar quando passar pela catraca."
_NO_TIMER = "Você não tem um cronômetro ativo. Use /registrar para começar."
_RESUMED = "Cronômetro retomado. Toque em /parar quando passar pela catraca."
_NOTHING_PENDING = "Não há nada para confirmar."
_TOO_LONG = "Tempo muito longo para ser real — não registrado."


def location_request_keyboard() -> ReplyKeyboardMarkup:
    """A one-shot keyboard whose single button shares the user's location."""
    button = KeyboardButton("📍 Enviar localização", request_location=True)
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)


def decision_keyboard() -> InlineKeyboardMarkup:
    """Confirm-or-resume choice shown when the user stops the timer."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data=_CONFIRM),
                InlineKeyboardButton("⏳ Ainda na fila", callback_data=_RESUME),
            ]
        ]
    )


def confirm_prompt(seconds: int) -> str:
    """Ask the user to confirm the measured wait before it is recorded."""
    return f"Você esperou {format_estimate(seconds)}. Confirmar o registro?"


def confirmation(seconds: int) -> str:
    """The user-facing confirmation after a recorded transit."""
    return f"Tempo registrado: {format_estimate(seconds)}. Obrigado por contribuir!"


def _rejection(verdict: ElapsedVerdict, clamp_min_seconds: int) -> str:
    """The message for a clamp-rejected transit (already not ACCEPTED).

    The too-short text names the *configured* floor rather than a hardcoded
    "1 minuto": with ``clamp_min_minutes = 0`` (empty-line installs) the floor
    is 0 and this branch never fires, but a fork that raises the floor must see
    its own minimum, not a stale constant.
    """
    if verdict is ElapsedVerdict.TOO_SHORT:
        minutes = clamp_min_seconds // SECONDS_PER_MINUTE
        return f"Tempo muito curto (mínimo {minutes} min) — não registrado."
    return _TOO_LONG


class RegisterTimer:
    """Wires /registrar, the location check, /parar, and confirm/resume."""

    def __init__(
        self,
        lines: tuple[Line, ...],
        preferences: LinePreferenceStore,
        openness: OpennessService,
        recorder: SubmissionRecorder,
        geofence: Geofence,
        config: EstimationConfig,
        clock: Callable[[], datetime],
    ) -> None:
        self._lines = lines
        self._preferences = preferences
        self._openness = openness
        self._recorder = recorder
        self._geofence = geofence
        self._config = config
        self._clock = clock

    def register(self, application: Application) -> None:
        """Add the start, stop, location, and confirm/resume handlers."""
        application.add_handler(CommandHandler(START_COMMAND, self.start))
        application.add_handler(CommandHandler(STOP_COMMAND, self.stop))
        application.add_handler(MessageHandler(filters.LOCATION, self.on_location))
        application.add_handler(
            CallbackQueryHandler(self.on_decision, pattern=DECISION_PATTERN)
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """``/registrar`` — gate the request, then ask for the user's location."""
        user_id = update.effective_user.id
        line = chosen_line(self._preferences, self._lines, user_id)
        if line is None:
            await update.effective_message.reply_text(NO_LINE)
            return
        status = self._openness.status(self._clock())
        if not status.is_open:
            await update.effective_message.reply_text(closed_message(status))
            return
        if self._recorder.already_submitted(user_id, self._clock()):
            await update.effective_message.reply_text(_ALREADY)
            return
        context.user_data["awaiting_line"] = line.id
        await update.effective_message.reply_text(
            _START_PROMPT, reply_markup=location_request_keyboard()
        )

    async def on_location(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Presence check: start the timer iff the shared location is in range."""
        line_id = context.user_data.get("awaiting_line")
        if line_id is None:
            await update.effective_message.reply_text(_NEED_START)
            return
        where = update.effective_message.location
        if not within_radius(self._geofence, where.latitude, where.longitude):
            # Out of range: keep the request so they can retry once closer. The
            # coordinates are not stored — only the in/out verdict is used.
            await update.effective_message.reply_text(_OUTSIDE)
            return
        del context.user_data["awaiting_line"]
        context.user_data["timer_start"] = self._clock()
        context.user_data["timer_line"] = line_id
        await update.effective_message.reply_text(
            _STARTED, reply_markup=ReplyKeyboardRemove()
        )

    async def stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """``/parar`` — measure the wait and ask the user to confirm or resume."""
        start = context.user_data.get("timer_start")
        if start is None:
            await update.effective_message.reply_text(_NO_TIMER)
            return
        seconds = elapsed_seconds(start, self._clock())
        context.user_data["pending_seconds"] = seconds
        await update.effective_message.reply_text(
            confirm_prompt(seconds), reply_markup=decision_keyboard()
        )

    async def on_decision(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Confirm records the pending wait; resume keeps the original timer."""
        query = update.callback_query
        await query.answer()
        if query.data == _RESUME:
            context.user_data.pop("pending_seconds", None)
            await query.edit_message_text(_RESUMED)
            return
        await self._record_pending(update.effective_user.id, context, query)

    async def _record_pending(
        self, user_id: int, context: ContextTypes.DEFAULT_TYPE, query: object
    ) -> None:
        seconds = context.user_data.pop("pending_seconds", None)
        start = context.user_data.get("timer_start")
        line_id = context.user_data.get("timer_line")
        if seconds is None or start is None or line_id is None:
            await query.edit_message_text(_NOTHING_PENDING)
            return
        self._clear_timer(context)
        verdict = classify_elapsed(seconds, self._config)
        if verdict is not ElapsedVerdict.ACCEPTED:
            await query.edit_message_text(_rejection(verdict, self._config.clamp_min))
            return
        self._recorder.record(user_id, line_id, start, seconds)
        await query.edit_message_text(confirmation(seconds))

    def _clear_timer(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        for key in ("timer_start", "timer_line", "pending_seconds"):
            context.user_data.pop(key, None)
