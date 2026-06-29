"""Per-user flood protection: a sliding-window rate limiter.

Caps how many actions one user may take in a window so a single user spamming
buttons or commands cannot exhaust the Pi (docs/PLAN.md §3). State is in-memory
and per-process — fine for a single bot instance. Time is passed in (monotonic
seconds), never read from a clock here, so the limiter is deterministic and
unit-testable.
"""

from __future__ import annotations

from collections import defaultdict, deque


class RateLimiter:
    """Allow at most ``max_events`` actions per ``window_seconds`` per user."""

    def __init__(self, max_events: int, window_seconds: float) -> None:
        if max_events <= 0 or window_seconds <= 0:
            raise ValueError(
                f"max_events and window_seconds must be positive, "
                f"got {max_events}, {window_seconds}"
            )
        self._max_events = max_events
        self._window = window_seconds
        self._events: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, user_id: int, now: float) -> bool:
        """Record an action at ``now`` and report whether it is permitted.

        A rejected action is *not* recorded, so being throttled does not
        extend the throttle — once older events age out, the user is free.
        """
        recent = self._events[user_id]
        cutoff = now - self._window
        while recent and recent[0] <= cutoff:
            recent.popleft()
        if len(recent) >= self._max_events:
            return False
        recent.append(now)
        return True
