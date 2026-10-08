"""Coherencia de los fixtures de demo, sin base de datos."""

from seeds.fixtures import INCIDENTS, ORGANIZATIONS, RESOURCES


def test_keys_and_codes_are_unique() -> None:
    assert len({f.key for f in INCIDENTS}) == len(INCIDENTS)
    assert len({f.code for f in RESOURCES}) == len(RESOURCES)


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
            # Cada paso es un cambio de estado o una nota, no ambos.
            assert (step.status is None) != (step.note is None), fixture.key
