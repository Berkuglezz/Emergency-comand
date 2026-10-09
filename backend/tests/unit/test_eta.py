"""ETA estimada (`app.domain.eta`): fórmula de CLAUDE.md §2.8."""

import math

import pytest

from app.domain.eta import (
    SINUOSITY_FACTOR,
    Eta,
    EtaOrigin,
    EtaUnavailable,
    estimate,
    haversine_km,
)

OVIEDO = (43.3614, -5.8494)
GIJON = (43.5357, -5.6615)


def test_haversine_matches_a_known_distance() -> None:
    # Oviedo-Gijón en línea recta: unos 24,6 km.
    assert haversine_km(OVIEDO, GIJON) == pytest.approx(24.6, abs=0.2)
    assert haversine_km(OVIEDO, OVIEDO) == 0


def test_eta_applies_sinuosity_and_rounds_minutes_up() -> None:
    eta = estimate(OVIEDO, GIJON, speed_kmh=60)

    assert isinstance(eta, Eta)
    road_km = haversine_km(OVIEDO, GIJON) * SINUOSITY_FACTOR
    assert eta.distance_km == round(road_km, 1)
    assert eta.minutes == math.ceil(road_km / 60 * 60)
    assert eta.origin is EtaOrigin.BASE


def test_slower_types_take_longer() -> None:
    fast = estimate(OVIEDO, GIJON, speed_kmh=65)
    slow = estimate(OVIEDO, GIJON, speed_kmh=45)
    assert isinstance(fast, Eta) and isinstance(slow, Eta)
    assert slow.minutes > fast.minutes
    assert slow.distance_km == fast.distance_km


def test_minutes_are_rounded_up_even_for_short_distances() -> None:
    eta = estimate(OVIEDO, (43.3624, -5.8494), speed_kmh=60)  # ≈ 110 m
    assert isinstance(eta, Eta)
    assert eta.minutes == 1


def test_eta_without_coordinates_explains_why() -> None:
    assert estimate(OVIEDO, None, 60) is EtaUnavailable.INCIDENT_WITHOUT_COORDINATES
    assert estimate(None, GIJON, 60) is EtaUnavailable.RESOURCE_WITHOUT_POSITION


def test_origin_kind_is_kept_for_phase_5() -> None:
    eta = estimate(OVIEDO, GIJON, 60, EtaOrigin.LAST_POSITION)
    assert isinstance(eta, Eta)
    assert eta.origin is EtaOrigin.LAST_POSITION
