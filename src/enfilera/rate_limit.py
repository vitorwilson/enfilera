"""Per-user flood protection: a sliding-window rate limiter.

Caps how many actions one user may take in a window so a single user spamming
buttons or commands cannot exhaust the Pi (docs/PLAN.md §3). State is in-memory
and per-process — fine for a single bot instance. Time is passed in (monotonic
seconds), never read from a clock here, so the limiter is deterministic and
unit-testable.

The bot is public — any Telegram user can message it — so the per-user state
must not accumulate one entry per sender forever. Every ``sweep_every`` calls,
idle users (no event left inside the window) are dropped, bounding memory to
the users actually active in the recent window.
"""

from __future__ import annotations

from collections import defaultdict, deque

# Run the idle-eviction sweep once per this many calls — amortized O(1) per
# call, so the hot path stays cheap while memory stays bounded.
_DEFAULT_SWEEP_EVERY = 1000


class RateLimiter:
    """Allow at most ``max_events`` actions per ``window_seconds`` per user."""

    def __init__(
        self,
        max_events: int,
        window_seconds: float,
        sweep_every: int = _DEFAULT_SWEEP_EVERY,
    ) -> None:
        if max_events <= 0 or window_seconds <= 0:
            raise ValueError(
                f"max_events and window_seconds must be positive, "
                f"got {max_events}, {window_seconds}"
            )
        if sweep_every <= 0:
            raise ValueError(f"sweep_every must be positive, got {sweep_every}")
        self._max_events = max_events
        self._window = window_seconds
        self._sweep_every = sweep_every
        self._events: dict[int, deque[float]] = defaultdict(deque)
        self._calls_since_sweep = 0

    def allow(self, user_id: int, now: float) -> bool:
        """Record an action at ``now`` and report whether it is permitted.

        A rejected action is *not* recorded, so being throttled does not
        extend the throttle — once older events age out, the user is free.
        """
        self._maybe_evict_idle(now)
        recent = self._events[user_id]
        cutoff = now - self._window
        while recent and recent[0] <= cutoff:
            recent.popleft()
        if len(recent) >= self._max_events:
            return False
        recent.append(now)
        return True

    @property
    def tracked_users(self) -> int:
        """How many users currently hold state (bounded by recent activity)."""
        return len(self._events)

    def _maybe_evict_idle(self, now: float) -> None:
        """Periodically drop users whose last event has left the window."""
        self._calls_since_sweep += 1
        if self._calls_since_sweep < self._sweep_every:
            return
        self._calls_since_sweep = 0
        cutoff = now - self._window
        idle = [
            user_id
            for user_id, events in self._events.items()
            if not events or events[-1] <= cutoff
        ]
        for user_id in idle:
            del self._events[user_id]
