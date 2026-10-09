"""Datos de demostración (solo entorno `development`).

Todo es ficticio y está marcado como simulado, para que nunca se confunda con
un servicio real:

- organizaciones con código `sim-…` y "(simulado)" en el nombre;
- emails del dominio reservado `.test` (RFC 2606), que no puede existir;
- recursos con código `SIM-…` y "(simulado)" en el nombre;
- incidentes con "(simulado)" en el título y ubicaciones genéricas a nivel de
  municipio, sin direcciones, teléfonos ni indicativos reales;
- coordenadas aproximadas (3 decimales, ≈100 m) en zonas genéricas del
  municipio, nunca sobre instalaciones de emergencias (hospitales, parques de
  bomberos, comisarías). Algunos incidentes no tienen coordenadas a propósito,
  para mostrar ese caso en la demo.

Las horas de recursos e incidentes son relativas al momento de ejecutar el seed.
"""

from dataclasses import dataclass, field
from typing import Any

from app.domain.enums import (
    IncidentPriority,
    IncidentStatus,
    ReleaseReason,
    ResourceStatus,
    RoleCode,
)
from app.domain.incident_rules import (
    INITIAL_STATUS,
    TERMINAL_STATUSES,
    status_after_assignment,
    status_after_last_release,
)


@dataclass(frozen=True, slots=True)
class DemoOrganization:
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class DemoUser:
    email: str
    full_name: str
    role: RoleCode
    organization_code: str


ORGANIZATIONS: tuple[DemoOrganization, ...] = (
    DemoOrganization(
        code="sim-coordinacion-asturias",
        name="Centro de Coordinación Demo Asturias (simulado)",
    ),
    DemoOrganization(
        code="sim-bomberos-oviedo",
        name="Parque de Bomberos Demo Oviedo (simulado)",
    ),
    DemoOrganization(
        code="sim-sanitario-gijon",
        name="Servicio Sanitario Demo Gijón (simulado)",
    ),
    DemoOrganization(
        code="sim-proteccion-civil-aviles",
        name="Protección Civil Demo Avilés (simulado)",
    ),
)

USERS: tuple[DemoUser, ...] = (
    DemoUser(
        email="admin@demo.emergency-command.test",
        full_name="Administración Demo",
        role=RoleCode.ADMIN,
        organization_code="sim-coordinacion-asturias",
    ),
    DemoUser(
        email="coordinador@demo.emergency-command.test",
        full_name="Coordinación Demo",
        role=RoleCode.COORDINATOR,
        organization_code="sim-coordinacion-asturias",
    ),
    DemoUser(
        email="operador@demo.emergency-command.test",
        full_name="Operación Demo",
        role=RoleCode.OPERATOR,
        organization_code="sim-bomberos-oviedo",
    ),
)


# --- Recursos ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DemoBase:
    """Base simulada de un recurso: municipio y coordenadas aproximadas
    (3 decimales) en una zona genérica, nunca sobre una instalación real."""

    municipality: str
    coordinates: tuple[float, float]
    description: str = "Base (ubicación simulada)"


@dataclass(frozen=True, slots=True)
class DemoResource:
    code: str
    name: str
    type_code: str
    organization_code: str
    base: DemoBase
    status: ResourceStatus
    # Minutos desde el último cambio de estado.
    status_minutes_ago: int


# Bases simuladas: los recursos de una organización en un municipio comparten
# punto (cada uno con su propia fila `Location`).
_BASE_BOV_OVIEDO = DemoBase("Oviedo", (43.352, -5.873))
_BASE_BOV_SIERO = DemoBase("Siero", (43.386, -5.672))
_BASE_SGI_GIJON = DemoBase("Gijón", (43.528, -5.675))
_BASE_SGI_OVIEDO = DemoBase("Oviedo", (43.366, -5.83))
_BASE_PCA_AVILES = DemoBase("Avilés", (43.548, -5.93))
_BASE_CAS_OVIEDO = DemoBase("Oviedo", (43.36, -5.855))
_BASE_CAS_SIERO = DemoBase("Siero", (43.4, -5.645))

_BOV = "sim-bomberos-oviedo"
_SGI = "sim-sanitario-gijon"
_PCA = "sim-proteccion-civil-aviles"
_CAS = "sim-coordinacion-asturias"
_AV = ResourceStatus.AVAILABLE
_IN = ResourceStatus.IN_SERVICE
_OUT = ResourceStatus.OUT_OF_SERVICE

RESOURCES: tuple[DemoResource, ...] = (
    DemoResource(
        "SIM-BOV-01", "Autobomba 1 (simulado)", "fire_engine", _BOV, _BASE_BOV_OVIEDO, _IN, 87
    ),
    DemoResource(
        "SIM-BOV-02", "Autobomba 2 (simulado)", "fire_engine", _BOV, _BASE_BOV_OVIEDO, _IN, 21
    ),
    DemoResource(
        "SIM-BOV-03", "Autobomba 3 (simulado)", "fire_engine", _BOV, _BASE_BOV_OVIEDO, _AV, 640
    ),
    DemoResource(
        "SIM-BOV-04", "Autobomba 4 (simulado)", "fire_engine", _BOV, _BASE_BOV_SIERO, _OUT, 2900
    ),
    DemoResource(
        "SIM-BOV-05",
        "Vehículo de rescate 1 (simulado)",
        "rescue_vehicle",
        _BOV,
        _BASE_BOV_OVIEDO,
        _IN,
        220,
    ),
    DemoResource(
        "SIM-BOV-06",
        "Vehículo de rescate 2 (simulado)",
        "rescue_vehicle",
        _BOV,
        _BASE_BOV_OVIEDO,
        _AV,
        35,
    ),
    DemoResource(
        "SIM-BOV-07",
        "Vehículo de mando 1 (simulado)",
        "command_vehicle",
        _BOV,
        _BASE_BOV_OVIEDO,
        _AV,
        900,
    ),
    DemoResource(
        "SIM-SGI-01",
        "Ambulancia SVA 1 (simulado)",
        "ambulance_advanced",
        _SGI,
        _BASE_SGI_GIJON,
        _IN,
        2,
    ),
    DemoResource(
        "SIM-SGI-02",
        "Ambulancia SVA 2 (simulado)",
        "ambulance_advanced",
        _SGI,
        _BASE_SGI_GIJON,
        _AV,
        380,
    ),
    DemoResource(
        "SIM-SGI-03",
        "Ambulancia SVB 1 (simulado)",
        "ambulance_basic",
        _SGI,
        _BASE_SGI_GIJON,
        _AV,
        120,
    ),
    DemoResource(
        "SIM-SGI-04",
        "Ambulancia SVB 2 (simulado)",
        "ambulance_basic",
        _SGI,
        _BASE_SGI_GIJON,
        _AV,
        260,
    ),
    DemoResource(
        "SIM-SGI-05",
        "Ambulancia SVB 3 (simulado)",
        "ambulance_basic",
        _SGI,
        _BASE_SGI_OVIEDO,
        _OUT,
        1500,
    ),
    DemoResource(
        "SIM-PCA-01",
        "Unidad de protección civil 1 (simulado)",
        "civil_protection_unit",
        _PCA,
        _BASE_PCA_AVILES,
        _IN,
        30,
    ),
    DemoResource(
        "SIM-PCA-02",
        "Unidad de protección civil 2 (simulado)",
        "civil_protection_unit",
        _PCA,
        _BASE_PCA_AVILES,
        _AV,
        1370,
    ),
    DemoResource(
        "SIM-PCA-03",
        "Apoyo logístico 1 (simulado)",
        "logistics_support",
        _PCA,
        _BASE_PCA_AVILES,
        _AV,
        1100,
    ),
    DemoResource(
        "SIM-PCA-04",
        "Apoyo logístico 2 (simulado)",
        "logistics_support",
        _PCA,
        _BASE_PCA_AVILES,
        _AV,
        95,
    ),
    DemoResource(
        "SIM-CAS-01",
        "Vehículo de mando 2 (simulado)",
        "command_vehicle",
        _CAS,
        _BASE_CAS_OVIEDO,
        _AV,
        1800,
    ),
    DemoResource(
        "SIM-CAS-02",
        "Apoyo logístico 3 (simulado)",
        "logistics_support",
        _CAS,
        _BASE_CAS_SIERO,
        _AV,
        3000,
    ),
)


# --- Incidentes -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DemoStep:
    """Paso del historial, `minute` minutos después de la notificación. Exactamente
    una acción: cambio de estado, nota, asignar un recurso (código), marcar su
    llegada o retirarlo con un motivo."""

    minute: int
    status: IncidentStatus | None = None
    reason: str | None = None
    note: str | None = None
    assign: str | None = None
    arrive: str | None = None
    release: str | None = None
    release_reason: ReleaseReason | None = None

    @property
    def actions(self) -> int:
        return sum(
            value is not None
            for value in (self.status, self.note, self.assign, self.arrive, self.release)
        )


@dataclass(frozen=True, slots=True)
class DemoIncident:
    # Clave estable del fixture: de ella sale el id (UUIDv5).
    key: str
    type_code: str
    title: str
    priority: IncidentPriority
    municipality: str
    location_description: str
    # (latitud, longitud) aproximadas; None = sin coordenadas a propósito.
    coordinates: tuple[float, float] | None
    # Minutos entre la notificación y la ejecución del seed.
    reported_minutes_ago: int
    steps: tuple[DemoStep, ...] = ()
    description: str | None = None
    affected_people: int | None = None
    details: dict[str, Any] = field(default_factory=dict)
    parent_key: str | None = None

    @property
    def status(self) -> IncidentStatus:
        """Estado final del historial, con los cambios manuales y los automáticos
        de la asignación de recursos (mismas reglas que el servicio)."""
        status = INITIAL_STATUS
        active: set[str] = set()
        for step in sorted(self.steps, key=lambda s: s.minute):
            if step.status is not None:
                status = step.status
                if status in TERMINAL_STATUSES:
                    active.clear()
            elif step.assign:
                active.add(step.assign)
                status = status_after_assignment(status)
            elif step.release:
                active.discard(step.release)
                if not active:
                    status = status_after_last_release(status)
        return status


_ST = IncidentStatus
_PR = IncidentPriority
_RR = ReleaseReason

# Ordenados del más antiguo al más reciente: así los códigos `INC-` siguen el
# orden de notificación. El padre va siempre antes que sus hijos.
INCIDENTS: tuple[DemoIncident, ...] = (
    # --- Ya cerrados ------------------------------------------------------------
    DemoIncident(
        key="hazmat-aviles",
        type_code="hazmat",
        title="Fuga de sustancia en polígono industrial (simulado)",
        priority=_PR.HIGH,
        municipality="Avilés",
        location_description="Polígono industrial (ubicación simulada)",
        coordinates=(43.574, -5.912),
        reported_minutes_ago=1620,
        affected_people=0,
        steps=(
            DemoStep(6, _ST.ASSESSING),
            DemoStep(12, assign="SIM-PCA-02"),
            DemoStep(18, _ST.IN_PROGRESS),
            DemoStep(40, note="Perímetro de seguridad establecido (simulado)"),
            DemoStep(130, _ST.CONTROLLED),
            DemoStep(250, _ST.CLOSED),
        ),
    ),
    DemoIncident(
        key="traffic-gijon-closed",
        type_code="traffic_accident",
        title="Salida de vía sin heridos (simulado)",
        priority=_PR.LOW,
        municipality="Gijón",
        location_description="Vía de circunvalación (ubicación simulada)",
        coordinates=(43.522, -5.677),
        reported_minutes_ago=610,
        affected_people=0,
        steps=(
            DemoStep(9, _ST.ASSESSING),
            DemoStep(20, _ST.IN_PROGRESS),
            DemoStep(48, _ST.CONTROLLED),
            DemoStep(75, _ST.CLOSED),
        ),
    ),
    # --- Temporal: incidente padre con dos hijos ------------------------------------
    DemoIncident(
        key="storm-central",
        type_code="severe_weather",
        title="Temporal de viento y lluvia en la zona central (simulado)",
        priority=_PR.HIGH,
        municipality="Oviedo",
        location_description="Zona central de Asturias (ubicación simulada)",
        # Episodio que afecta a una zona amplia: no tiene un único punto.
        coordinates=None,
        reported_minutes_ago=300,
        description="Episodio de viento y lluvia intensa que agrupa varios avisos (simulado).",
        steps=(
            DemoStep(5, _ST.ASSESSING),
            DemoStep(22, _ST.IN_PROGRESS),
            DemoStep(45, note="Seguimiento meteorológico activado (simulado)"),
        ),
    ),
    DemoIncident(
        key="storm-flood-gijon",
        type_code="flood",
        title="Inundación en zona baja (simulado)",
        priority=_PR.HIGH,
        municipality="Gijón",
        location_description="Zona baja junto al cauce (ubicación simulada)",
        coordinates=(43.535, -5.637),
        reported_minutes_ago=240,
        affected_people=12,
        details={"water_level_cm": 60},
        parent_key="storm-central",
        steps=(
            DemoStep(10, _ST.ASSESSING),
            DemoStep(20, assign="SIM-BOV-05"),
            DemoStep(26, _ST.IN_PROGRESS),
            DemoStep(60, arrive="SIM-BOV-05"),
            DemoStep(90, note="Nivel del agua estable (simulado)"),
        ),
    ),
    DemoIncident(
        key="storm-landslide-mieres",
        type_code="landslide",
        title="Desprendimiento en carretera local (simulado)",
        priority=_PR.MEDIUM,
        municipality="Mieres",
        location_description="Carretera local de montaña (ubicación simulada)",
        coordinates=(43.237, -5.745),
        reported_minutes_ago=200,
        parent_key="storm-central",
        steps=(DemoStep(15, _ST.ASSESSING),),
    ),
    # --- Activos y recientes ----------------------------------------------------------
    DemoIncident(
        key="mountain-rescue-aller",
        type_code="mountain_rescue",
        title="Rescate de senderista en ruta de montaña (simulado)",
        priority=_PR.MEDIUM,
        municipality="Aller",
        location_description="Ruta de montaña señalizada (ubicación simulada)",
        coordinates=(43.088, -5.59),
        reported_minutes_ago=150,
        affected_people=1,
        steps=(
            DemoStep(10, _ST.ASSESSING),
            DemoStep(20, assign="SIM-BOV-06"),
            DemoStep(30, _ST.IN_PROGRESS),
            DemoStep(70, arrive="SIM-BOV-06"),
            DemoStep(112, _ST.CONTROLLED),
            DemoStep(115, release="SIM-BOV-06", release_reason=_RR.COMPLETED),
        ),
    ),
    DemoIncident(
        key="wildfire-siero",
        type_code="wildfire",
        title="Incendio forestal en monte comunal (simulado)",
        priority=_PR.CRITICAL,
        municipality="Siero",
        location_description="Zona forestal (ubicación simulada)",
        coordinates=(43.36, -5.61),
        reported_minutes_ago=95,
        details={"affected_hectares": "12.50", "vegetation": "forest"},
        steps=(
            DemoStep(3, _ST.ASSESSING),
            DemoStep(8, assign="SIM-BOV-01"),
            DemoStep(12, _ST.IN_PROGRESS),
            DemoStep(30, arrive="SIM-BOV-01"),
            DemoStep(50, note="Frente principal en zona de matorral (simulado)"),
            DemoStep(74, assign="SIM-BOV-02"),
        ),
    ),
    DemoIncident(
        key="medical-oviedo-cancelled",
        type_code="medical_emergency",
        title="Aviso por persona indispuesta (simulado)",
        priority=_PR.MEDIUM,
        municipality="Oviedo",
        location_description="Vía pública (ubicación simulada)",
        coordinates=(43.361, -5.844),
        reported_minutes_ago=70,
        steps=(DemoStep(6, _ST.CANCELLED, reason="Aviso duplicado (simulado)"),),
    ),
    DemoIncident(
        key="water-rescue-gijon",
        type_code="water_rescue",
        title="Embarcación a la deriva sin ocupantes (simulado)",
        priority=_PR.LOW,
        municipality="Gijón",
        location_description="Zona costera (ubicación simulada)",
        coordinates=(43.56, -5.668),
        reported_minutes_ago=45,
        affected_people=0,
        steps=(
            DemoStep(8, _ST.ASSESSING),
            DemoStep(15, assign="SIM-PCA-01"),
            DemoStep(20, _ST.IN_PROGRESS),
        ),
    ),
    DemoIncident(
        key="structure-fire-aviles",
        type_code="structure_fire",
        title="Incendio en nave industrial (simulado)",
        priority=_PR.CRITICAL,
        municipality="Avilés",
        location_description="Nave en zona industrial (ubicación simulada)",
        coordinates=(43.548, -5.895),
        reported_minutes_ago=25,
        affected_people=3,
        steps=(DemoStep(4, _ST.ASSESSING),),
    ),
    DemoIncident(
        key="traffic-oviedo",
        type_code="traffic_accident",
        title="Colisión múltiple en vía de acceso (simulado)",
        priority=_PR.HIGH,
        municipality="Oviedo",
        location_description="Vía de acceso a la ciudad (ubicación simulada)",
        coordinates=(43.372, -5.815),
        reported_minutes_ago=8,
        affected_people=4,
    ),
    DemoIncident(
        key="medical-gijon",
        type_code="medical_emergency",
        title="Atención sanitaria urgente en vía pública (simulado)",
        priority=_PR.HIGH,
        municipality="Gijón",
        location_description="Paseo marítimo (ubicación simulada)",
        # Aviso recién recibido: la posición aún no está confirmada.
        coordinates=None,
        reported_minutes_ago=3,
        affected_people=1,
        steps=(DemoStep(1, assign="SIM-SGI-01"),),
    ),
)
