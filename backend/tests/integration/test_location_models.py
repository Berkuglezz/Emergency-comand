"""Ubicaciones (Fase 3.1) contra el esquema real de la migración: PostGIS,
`geometry(Point, 4326)`, índice GiST y relación 1:1 con el incidente."""

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import IncidentPriority, IncidentStatus
from app.models import Incident, IncidentType, Location
from app.repositories.incidents import IncidentRepository


async def _new_incident(session: AsyncSession, location: Location) -> Incident:
    incident_type = (
        await session.scalars(select(IncidentType).where(IncidentType.code == "flood"))
    ).one()
    incident = Incident(
        code=await IncidentRepository(session).next_code(),
        type_id=incident_type.id,
        title="Incidente de prueba",
        status=IncidentStatus.RECEIVED,
        priority=IncidentPriority.MEDIUM,
        location=location,
    )
    session.add(incident)
    await session.flush()
    return incident


async def test_geom_column_is_a_wgs84_point(session: AsyncSession) -> None:
    row = (
        await session.execute(
            text(
                "SELECT type, srid FROM geometry_columns "
                "WHERE f_table_name = 'locations' AND f_geometry_column = 'geom'"
            )
        )
    ).one()
    assert tuple(row) == ("POINT", 4326)


async def test_geom_has_a_gist_index(session: AsyncSession) -> None:
    definition = await session.scalar(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_locations_geom'")
    )
    assert definition is not None
    assert "USING gist (geom)" in definition


async def test_location_without_coordinates(session: AsyncSession) -> None:
    location = Location(municipality="Oviedo")
    session.add(location)
    await session.flush()
    await session.refresh(location)

    assert location.geom is None
    assert location.description is None
    assert location.created_at.tzinfo is not None


async def test_location_stores_a_point(session: AsyncSession) -> None:
    # WKT: longitud primero, luego latitud.
    location = Location(municipality="Gijón", geom=WKTElement("POINT(-5.662 43.545)", srid=4326))
    session.add(location)
    await session.flush()

    longitude, latitude, srid = (
        await session.execute(
            select(
                func.ST_X(Location.geom), func.ST_Y(Location.geom), func.ST_SRID(Location.geom)
            ).where(Location.id == location.id)
        )
    ).one()
    assert (longitude, latitude, srid) == (pytest.approx(-5.662), pytest.approx(43.545), 4326)


@pytest.mark.parametrize(
    "geometry",
    [
        "ST_GeomFromText('POINT(-5.66 43.54)', 3857)",  # otro SRID
        "ST_GeomFromText('LINESTRING(-5.66 43.54, -5.84 43.36)', 4326)",  # no es un punto
    ],
)
async def test_geom_only_accepts_wgs84_points(session: AsyncSession, geometry: str) -> None:
    with pytest.raises(DBAPIError):
        await session.execute(
            text(f"INSERT INTO locations (municipality, geom) VALUES ('Oviedo', {geometry})")  # noqa: S608 — valores fijos del test
        )


async def test_point_without_srid_takes_the_column_srid(session: AsyncSession) -> None:
    # Comportamiento de PostGIS con typmod: SRID 0 (desconocido) pasa a 4326.
    srid = await session.scalar(
        text(
            "INSERT INTO locations (municipality, geom)"
            " VALUES ('Oviedo', ST_GeomFromText('POINT(-5.66 43.54)')) RETURNING ST_SRID(geom)"
        )
    )
    assert srid == 4326


async def test_incident_has_its_own_location(session: AsyncSession) -> None:
    incident = await _new_incident(session, Location(municipality="Avilés", description="Puerto"))

    loaded = (
        await session.scalars(
            select(Location)
            .join(Incident, Incident.location_id == Location.id)
            .where(Incident.id == incident.id)
        )
    ).one()
    assert (loaded.municipality, loaded.description) == ("Avilés", "Puerto")


async def test_two_incidents_cannot_share_a_location(session: AsyncSession) -> None:
    first = await _new_incident(session, Location(municipality="Oviedo"))
    second = await _new_incident(session, Location(municipality="Gijón"))

    with pytest.raises(IntegrityError):
        await session.execute(
            text("UPDATE incidents SET location_id = :location WHERE id = :id"),
            {"location": first.location_id, "id": second.id},
        )


async def test_location_of_an_incident_cannot_be_deleted(session: AsyncSession) -> None:
    incident = await _new_incident(session, Location(municipality="Oviedo"))

    with pytest.raises(IntegrityError):
        await session.execute(
            text("DELETE FROM locations WHERE id = :id"), {"id": incident.location_id}
        )
