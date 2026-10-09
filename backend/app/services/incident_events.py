"""Registro de entradas del historial del incidente (`IncidentEvent`).

Lo usan los servicios de incidentes y de asignaciones. Cada entrada se inserta
en la misma transacción que el cambio que describe.
"""

from datetime import datetime, timedelta
from typing import Any

from app.domain.enums import IncidentEventType
from app.models import Incident, IncidentEvent, User
from app.repositories.incidents import IncidentRepository


class EventRecorder:
    """Inserta las entradas de historial de una operación con la hora real en
    que se produjo. El timeline se ordena por `(occurred_at, id)`: cada entrada
    de la misma operación suma 1 µs, para que se lean en el orden en que se
    registraron (p. ej. «recurso asignado» antes del cambio de estado que
    provoca)."""

    def __init__(self, repository: IncidentRepository, actor: User, now: datetime) -> None:
        self._repository = repository
        self._actor = actor
        self._now = now
        self._count = 0

    def record(
        self, incident: Incident, event_type: IncidentEventType, payload: dict[str, Any]
    ) -> IncidentEvent:
        event = IncidentEvent(
            incident_id=incident.id,
            event_type=event_type,
            occurred_at=self._now + timedelta(microseconds=self._count),
            actor_user_id=self._actor.id,
            payload=payload,
            is_simulated=incident.is_simulated,
        )
        self._repository.add_event(event)
        self._count += 1
        return event
