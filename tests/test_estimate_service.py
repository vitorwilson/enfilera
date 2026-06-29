"""Tests for the estimation service over a real in-memory sample store.

Exercises the full wire-up: windowed reads (history vs today), the block-wise
fallback fold, and the estimator's gating — end to end. Fixed dates: every
Tuesday in June 2026 (2, 9, 16, 23, 30) is an operating day, so prior Tuesdays
are the historical baseline for a Tuesday-noon bucket.
"""

import sqlite3
from datetime import datetime, time
from zoneinfo import ZoneInfo

from enfilera.estimate_service import EstimationService
from enfilera.estimation_config import EstimationConfig
from enfilera.samples_store import SampleStore
from enfilera.schedule import build_schedule

SP = ZoneInfo("America/Sao_Paulo")
RETENTION = 30


def _schedule():
    return build_schedule(
        {
            "restaurant": {"timezone": "America/Sao_Paulo"},
            "schedule": {
                "operating_days": [1, 2, 3, 4, 5],
                "block_minutes": 60,
                "periods": [
                    {"id": "lunch", "start": "10:30", "end": "14:30"},
                    {"id": "dinner", "start": "17:00", "end": "20:00"},
                ],
            },
        }
    )


def _config() -> EstimationConfig:
    return EstimationConfig(
        min_samples=3, default_seed=60, clamp_min=60, clamp_max=3600, mad_k=3.0
    )


def _service(conn: sqlite3.Connection) -> tuple[EstimationService, SampleStore]:
    store = SampleStore(conn)
    return EstimationService(store, _schedule(), _config(), RETENTION), store


def _sp(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SP)


def test_closed_outside_periods_returns_none(memory_db: sqlite3.Connection) -> None:
    service, _ = _service(memory_db)
    assert service.current_estimate(_sp(2026, 6, 30, 15, 30), "card") is None


def test_enough_samples_uses_robust_aggregate(memory_db: sqlite3.Connection) -> None:
    service, store = _service(memory_db)
    for value in (600, 660, 720):
        store.add("card", 2, time(12, 0), value, _sp(2026, 6, 30, 12, 5))
    assert service.current_estimate(_sp(2026, 6, 30, 12, 15), "card") == 660


def test_sparse_block_falls_back_to_previous_block(
    memory_db: sqlite3.Connection,
) -> None:
    service, store = _service(memory_db)
    for _ in range(3):
        store.add("card", 2, time(11, 0), 600, _sp(2026, 6, 30, 11, 5))
    store.add("card", 2, time(12, 0), 999, _sp(2026, 6, 30, 12, 5))  # sparse
    assert service.current_estimate(_sp(2026, 6, 30, 12, 15), "card") == 600


def test_first_block_sparse_falls_back_to_historical_seed(
    memory_db: sqlite3.Connection,
) -> None:
    service, store = _service(memory_db)
    # Prior Tuesdays at the 10:00 block form the baseline (centre 660).
    for day, value in ((23, 600), (16, 660), (9, 720)):
        store.add("card", 2, time(10, 0), value, _sp(2026, 6, day, 10, 45))
    # Today's lone sample is both sparse and a high outlier — rejected.
    store.add("card", 2, time(10, 0), 9999, _sp(2026, 6, 30, 10, 40))
    # 10:45 sits in the period's first block, so there is no previous block.
    assert service.current_estimate(_sp(2026, 6, 30, 10, 45), "card") == 660


def test_no_data_anywhere_returns_default_seed(
    memory_db: sqlite3.Connection,
) -> None:
    service, _ = _service(memory_db)
    assert service.current_estimate(_sp(2026, 6, 30, 10, 45), "card") == 60


def test_historical_baseline_excludes_today(memory_db: sqlite3.Connection) -> None:
    service, store = _service(memory_db)
    # A big cluster TODAY in the first block must not feed its own baseline.
    for _ in range(3):
        store.add("card", 2, time(10, 0), 3000, _sp(2026, 6, 30, 10, 40))
    # With no prior-day history, the baseline is None, so all three (within the
    # clamp) are aggregated — proving they came from the *today* window only.
    assert service.current_estimate(_sp(2026, 6, 30, 10, 45), "card") == 3000
