"""Tests for the geofence presence check.

A user ~10 m away is inside a 50 m fence; a user a few hundred metres away is
out. The distance is great-circle, so the two reference points below are a
known short hop apart at São Paulo's latitude.
"""

import pytest

from enfilera.geofence import Geofence, build_geofence, within_radius

CENTRE = Geofence(latitude=-23.559616, longitude=-46.731386, radius_m=50)


def _raw(**overrides: object) -> dict:
    restaurant = {"latitude": -23.559616, "longitude": -46.731386, "radius_m": 50}
    restaurant.update(overrides)
    return {"restaurant": restaurant}


# --- build_geofence ------------------------------------------------------


def test_build_geofence_parses_point_and_radius() -> None:
    fence = build_geofence(_raw())
    assert fence.latitude == -23.559616
    assert fence.radius_m == 50.0


@pytest.mark.parametrize("bad", [91, -91, 200])
def test_build_geofence_rejects_out_of_range_latitude(bad: float) -> None:
    with pytest.raises(ValueError, match="latitude"):
        build_geofence(_raw(latitude=bad))


def test_build_geofence_rejects_out_of_range_longitude() -> None:
    with pytest.raises(ValueError, match="longitude"):
        build_geofence(_raw(longitude=181))


def test_build_geofence_rejects_non_positive_radius() -> None:
    with pytest.raises(ValueError, match="radius_m"):
        build_geofence(_raw(radius_m=0))


# --- within_radius -------------------------------------------------------


def test_exact_centre_is_inside() -> None:
    assert within_radius(CENTRE, -23.559616, -46.731386) is True


def test_a_few_metres_away_is_inside() -> None:
    # ~11 m north (1e-4 degrees latitude ≈ 11 m).
    assert within_radius(CENTRE, -23.559516, -46.731386) is True


def test_far_away_is_outside() -> None:
    # ~1.1 km north (0.01 degrees latitude) is well outside a 50 m fence.
    assert within_radius(CENTRE, -23.549616, -46.731386) is False


def test_boundary_radius_is_generous_not_strict() -> None:
    # A tiny fence excludes a point that a large fence includes — sanity that
    # the radius actually gates the result.
    tiny = Geofence(latitude=0.0, longitude=0.0, radius_m=1)
    assert within_radius(tiny, 0.001, 0.0) is False
    big = Geofence(latitude=0.0, longitude=0.0, radius_m=1000)
    assert within_radius(big, 0.001, 0.0) is True
