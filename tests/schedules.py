"""The standard weekday lunch+dinner schedule, shared across tests.

Every handler/service test needs the same operating schedule (Mon–Fri, lunch
10:30–14:30, dinner 17:00–20:00, 60-min blocks); this builds it once so the
config lives in one place. ``timezone`` is a parameter only because the
openness tests exercise DST/zone handling against the same shape.
"""

from __future__ import annotations

from enfilera.schedule import Schedule, build_schedule


def make_schedule(timezone: str = "America/Sao_Paulo") -> Schedule:
    """Build the standard schedule, optionally in a different ``timezone``."""
    return build_schedule(
        {
            "restaurant": {"timezone": timezone},
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
