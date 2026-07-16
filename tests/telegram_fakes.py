"""Named fake Telegram objects shared across handler tests.

Handlers are driven with these instead of a live bot: they expose only the
attributes/coroutines the handlers touch and record what was sent, so a test
can assert on replies without any network. Kept in one place so each handler
test reuses the same fakes rather than redefining them.
"""

from __future__ import annotations


class FakeLocation:
    """A shared Telegram location (the only fields the geofence reads)."""

    def __init__(self, latitude: float, longitude: float) -> None:
        self.latitude = latitude
        self.longitude = longitude


class FakeMessage:
    """Records reply_text calls instead of sending to Telegram."""

    def __init__(self, location: FakeLocation | None = None) -> None:
        self.location = location
        self.replies: list[tuple[str, object]] = []

    async def reply_text(self, text: str, reply_markup: object = None) -> None:
        self.replies.append((text, reply_markup))


class FakeContext:
    """Carries per-user state, command args, and an error, like PTB's context."""

    def __init__(
        self, args: list[str] | None = None, error: BaseException | None = None
    ) -> None:
        self.user_data: dict[str, object] = {}
        # PTB fills context.args with the whitespace-split command arguments.
        self.args: list[str] = args or []
        # PTB sets context.error when dispatching to an error handler.
        self.error: BaseException | None = error


class FakeCallbackQuery:
    """A tapped inline button: carries data, records answer/edit calls."""

    def __init__(self, data: str) -> None:
        self.data = data
        self.answered = False
        self.edits: list[str] = []
        # Parallel to edits: the reply_markup passed with each edit (or None),
        # so a test can assert an edit re-rendered an inline keyboard.
        self.edit_markups: list[object] = []

    async def answer(self) -> None:
        self.answered = True

    async def edit_message_text(self, text: str, reply_markup: object = None) -> None:
        self.edits.append(text)
        self.edit_markups.append(reply_markup)


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class FakeUpdate:
    """Stand-in exposing only the attributes the handlers read."""

    def __init__(
        self,
        *,
        effective_message: FakeMessage | None = None,
        callback_query: FakeCallbackQuery | None = None,
        effective_user: FakeUser | None = None,
    ) -> None:
        self.effective_message = effective_message
        self.callback_query = callback_query
        self.effective_user = effective_user
