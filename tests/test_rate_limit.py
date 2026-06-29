"""Tests for the per-user sliding-window rate limiter.

Time is injected as monotonic seconds, so windows are exercised exactly with
no sleeping (F.I.R.S.T).
"""

import pytest

from enfilera.rate_limit import RateLimiter


def test_allows_up_to_the_limit() -> None:
    limiter = RateLimiter(max_events=3, window_seconds=10)
    assert [limiter.allow(1, now=0.0) for _ in range(3)] == [True, True, True]


def test_blocks_beyond_the_limit_within_window() -> None:
    limiter = RateLimiter(max_events=2, window_seconds=10)
    limiter.allow(1, now=0.0)
    limiter.allow(1, now=1.0)
    assert limiter.allow(1, now=2.0) is False


def test_window_slides_so_old_events_age_out() -> None:
    limiter = RateLimiter(max_events=2, window_seconds=10)
    limiter.allow(1, now=0.0)
    limiter.allow(1, now=1.0)
    # 11s after the first event, that event has left the window.
    assert limiter.allow(1, now=11.0) is True


def test_users_are_independent() -> None:
    limiter = RateLimiter(max_events=1, window_seconds=10)
    assert limiter.allow(1, now=0.0) is True
    assert limiter.allow(2, now=0.0) is True
    assert limiter.allow(1, now=0.0) is False


def test_rejected_action_does_not_extend_throttle() -> None:
    limiter = RateLimiter(max_events=1, window_seconds=10)
    limiter.allow(1, now=0.0)  # accepted
    assert limiter.allow(1, now=5.0) is False  # rejected, not recorded
    # 10s after the only recorded event it ages out, so this is allowed.
    assert limiter.allow(1, now=10.1) is True


@pytest.mark.parametrize("bad", [0, -1])
def test_rejects_non_positive_config(bad: int) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        RateLimiter(max_events=bad, window_seconds=10)


def test_rejects_non_positive_sweep_every() -> None:
    with pytest.raises(ValueError, match="sweep_every must be positive"):
        RateLimiter(max_events=1, window_seconds=10, sweep_every=0)


def test_idle_users_are_evicted_by_the_periodic_sweep() -> None:
    # Regression: a public bot gets one entry per distinct sender; without the
    # sweep, idle users' state would accumulate forever (a slow memory leak).
    limiter = RateLimiter(max_events=5, window_seconds=10, sweep_every=2)
    limiter.allow(1, now=0.0)  # user 1 acts once at t=0
    assert limiter.tracked_users == 1
    # By t=20, user 1's only event (t=0) has aged out of the 10s window; the
    # second call since the last sweep triggers eviction of that idle user.
    limiter.allow(2, now=20.0)
    limiter.allow(2, now=20.0)
    assert limiter.tracked_users == 1  # user 1 dropped; only user 2 remains


def test_sweep_keeps_users_still_active_in_the_window() -> None:
    limiter = RateLimiter(max_events=5, window_seconds=10, sweep_every=2)
    limiter.allow(1, now=0.0)
    limiter.allow(2, now=1.0)
    limiter.allow(1, now=5.0)  # call 2 → sweep at t=5; both still within window
    assert limiter.tracked_users == 2


def test_evicted_user_starts_fresh() -> None:
    limiter = RateLimiter(max_events=1, window_seconds=10, sweep_every=2)
    limiter.allow(1, now=0.0)
    limiter.allow(2, now=20.0)
    limiter.allow(2, now=20.0)  # sweep drops the idle user 1
    # User 1 returns much later: a clean slate, so its first action is allowed.
    assert limiter.allow(1, now=100.0) is True
