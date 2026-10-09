"""Coherencia de los fixtures de demo, sin base de datos."""

from app.domain.enums import RoleCode
from app.domain.geo import DEMO_AREA
from app.domain.incident_rules import ACTIVE_STATUSES
from seeds.fixtures import INCIDENTS, ORGANIZATIONS, RESOURCES, USERS


def test_keys_and_codes_are_unique() -> None:
    assert len({f.key for f in INCIDENTS}) == len(INCIDENTS)
    assert len({f.code for f in RESOURCES}) == len(RESOURCES)


def test_users_belong_to_demo_organizations_or_none() -> None:
    codes = {o.code for o in ORGANIZATIONS}
    assert all(u.organization_code is None or u.organization_code in codes for u in USERS)
    # Uno por rol como mínimo, y un operador sin organización (D3).
    assert {u.role for u in USERS} == set(RoleCode)
    assert any(u.role == RoleCode.OPERATOR and u.organization_code is None for u in USERS)
    assert all(u.email.endswith(".test") for u in USERS)


def test_resources_belong_to_demo_organizations() -> None:
    codes = {org.code for org in ORGANIZATIONS}
    assert all(f.organization_code in codes for f in RESOURCES)


def test_incidents_are_in_chronological_order() -> None:
    # Así los códigos `INC-` de la secuencia siguen el orden de notificación.
    ages = [f.reported_minutes_ago for f in INCIDENTS]
    assert ages == sorted(ages, reverse=True)


def test_parents_come_first_and_have_a_single_level() -> None:
    seen: dict[str, str | None] = {}
    for fixture in INCIDENTS:
        if fixture.parent_key is not None:
            assert fixture.parent_key in seen, fixture.key
            assert seen[fixture.parent_key] is None, "un hijo no puede tener hijos"
        seen[fixture.key] = fixture.parent_key


def test_history_steps_are_ordered_and_never_in_the_future() -> None:
    for fixture in INCIDENTS:
        minutes = [step.minute for step in fixture.steps]
        assert minutes == sorted(set(minutes)), fixture.key
        assert all(0 < minute < fixture.reported_minutes_ago for minute in minutes), fixture.key
        for step in fixture.steps:
            # Cada paso es exactamente una acción.
            assert step.actions == 1, fixture.key


def test_coordinates_are_approximate_and_inside_the_demo_area() -> None:
    located = [f for f in INCIDENTS if f.coordinates is not None]
    for fixture in located:
        assert fixture.coordinates is not None
        latitude, longitude = fixture.coordinates
        # Como mucho 3 decimales (≈100 m): no señalan ningún portal concreto.
        assert round(latitude, 3) == latitude and round(longitude, 3) == longitude, fixture.key
        assert DEMO_AREA.contains(latitude, longitude), fixture.key
    # Cada incidente en un punto distinto: ninguno queda oculto bajo otro.
    assert len({f.coordinates for f in located}) == len(located)


def test_some_active_incidents_have_no_coordinates_on_purpose() -> None:
    # La demo debe mostrar el caso «sin coordenadas» en el mapa.
    unlocated = [f for f in INCIDENTS if f.coordinates is None]
    assert unlocated
    assert all(f.status in ACTIVE_STATUSES for f in unlocated)


def test_resource_bases_are_inside_the_demo_area() -> None:
    for fixture in RESOURCES:
        latitude, longitude = fixture.base.coordinates
        assert round(latitude, 3) == latitude and round(longitude, 3) == longitude, fixture.code
        assert DEMO_AREA.contains(latitude, longitude), fixture.code
        assert "simulada" in fixture.base.description
