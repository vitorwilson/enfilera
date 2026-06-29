"""Presence check: is the user within the configured radius of the restaurant?

The timer can only be *started* when the user is physically at the cafeteria.
Their live location is compared to the configured centre and then discarded by
the caller — never stored (docs/PLAN.md §3). This module is pure geometry: the
great-circle (haversine) distance and a radius test, no Telegram or storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from enfilera.config_parsing import positive_number, section

# Mean Earth radius (metres). Distances are tens of metres, so the spherical
# approximation is far more precise than the geofence radius needs.
EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class Geofence:
    """The restaurant's location and the allowed start radius, in metres."""

    latitude: float
    longitude: float
    radius_m: float


def build_geofence(raw: dict) -> Geofence:
    """Parse and validate the geofence from the ``[restaurant]`` config.

    >>> build_geofence({"restaurant": {
    ...     "latitude": -23.5, "longitude": -46.7, "radius_m": 50}}).radius_m
    50.0
    """
    restaurant = section(raw, "restaurant")
    return Geofence(
        latitude=_coordinate(restaurant["latitude"], "latitude", 90.0),
        longitude=_coordinate(restaurant["longitude"], "longitude", 180.0),
        radius_m=positive_number(restaurant["radius_m"], "radius_m"),
    )


def within_radius(geofence: Geofence, latitude: float, longitude: float) -> bool:
    """Whether ``(latitude, longitude)`` is within the geofence radius.

    >>> fence = Geofence(-23.5, -46.7, 50)
    >>> within_radius(fence, -23.5, -46.7)
    True
    """
    distance = _haversine_m(geofence.latitude, geofence.longitude, latitude, longitude)
    return distance <= geofence.radius_m


def _coordinate(value: object, field: str, bound: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number, got {value!r}")
    if not -bound <= value <= bound:
        raise ValueError(f"{field} must be within ±{bound}, got {value!r}")
    return float(value)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))
