"""Ámbito organizativo de un usuario (CLAUDE.md §2.11, decisiones D1, D3 y D4).

Separa **qué** puede hacer un usuario (rol → permisos, `app.core.permissions`)
de **sobre qué organizaciones** puede hacerlo. Es lógica pura: sin base de
datos ni HTTP. El ámbito se calcula a partir del rol y de la organización del
usuario; ningún endpoint decide el suyo por su cuenta.

Se aplica en los servicios, después de cargar el recurso y antes de modificar
nada: al cambio de estado operativo de un recurso y a «en el lugar» (R.4), y a
asignar, retirar y reasignar, con los candidatos filtrados (R.5). La lectura
(R.6) se comprueba en la ficha y el listado de recursos; con D4 no restringe a
ningún rol, pero el patrón queda listo para ámbitos de lectura limitados.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from app.domain.enums import RoleCode
from app.domain.exceptions import NotFoundError, OutOfScopeError, PermissionDeniedError


@dataclass(frozen=True, slots=True)
class OrganizationAccess:
    """Organizaciones alcanzables: todas, o un conjunto concreto (quizá vacío)."""

    all_organizations: bool = False
    organization_ids: frozenset[uuid.UUID] = frozenset()

    @classmethod
    def everything(cls) -> "OrganizationAccess":
        return cls(all_organizations=True)

    @classmethod
    def nothing(cls) -> "OrganizationAccess":
        return cls()

    @classmethod
    def only(cls, *organization_ids: uuid.UUID) -> "OrganizationAccess":
        return cls(organization_ids=frozenset(organization_ids))

    def allows(self, organization_id: uuid.UUID) -> bool:
        return self.all_organizations or organization_id in self.organization_ids

    def as_filter(self) -> frozenset[uuid.UUID] | None:
        """Para filtrar consultas: `None` = sin restricción; si no, las
        organizaciones permitidas (un conjunto vacío no devuelve nada)."""
        return None if self.all_organizations else self.organization_ids


@dataclass(frozen=True, slots=True)
class AccessScope:
    """Ámbito de lectura y de escritura de un usuario."""

    read: OrganizationAccess
    write: OrganizationAccess

    def can_read(self, organization_id: uuid.UUID) -> bool:
        return self.read.allows(organization_id)

    def can_write(self, organization_id: uuid.UUID) -> bool:
        return self.write.allows(organization_id)

    def require_read(self, organization_id: uuid.UUID, *, not_found: str) -> None:
        """Comprobación de lectura (D5): fuera del ámbito, el elemento «no existe»
        (`NotFoundError` con el código de no encontrado de quien llama, 404),
        para no revelar su existencia. Con D4 todos los roles leen todas las
        organizaciones, así que hoy nunca se dispara."""
        if not self.can_read(organization_id):
            raise NotFoundError(not_found)

    def require_write(self, organization_id: uuid.UUID) -> None:
        """Única comprobación de escritura que usan los servicios: lanza
        `OutOfScopeError` (403) si la organización queda fuera del ámbito."""
        if not self.can_write(organization_id):
            raise OutOfScopeError()


def _whole_central(_: uuid.UUID | None) -> AccessScope:
    """Admin y coordinador (D1): leen y modifican en todas las organizaciones."""
    return AccessScope(read=OrganizationAccess.everything(), write=OrganizationAccess.everything())


def _own_organization(organization_id: uuid.UUID | None) -> AccessScope:
    """Operador (D3, D4): consulta todas las organizaciones (imagen operativa
    común) y solo modifica la suya; sin organización, no modifica ninguna."""
    write = (
        OrganizationAccess.only(organization_id)
        if organization_id is not None
        else OrganizationAccess.nothing()
    )
    return AccessScope(read=OrganizationAccess.everything(), write=write)


# Regla explícita para cada rol. Un rol sin regla no obtiene ningún ámbito.
SCOPE_RULES: dict[RoleCode, Callable[[uuid.UUID | None], AccessScope]] = {
    RoleCode.ADMIN: _whole_central,
    RoleCode.COORDINATOR: _whole_central,
    RoleCode.OPERATOR: _own_organization,
}


def scope_for(role: RoleCode, organization_id: uuid.UUID | None) -> AccessScope:
    """Ámbito de un usuario según su rol y su organización.

    Falla de forma cerrada: un rol sin regla explícita no recibe acceso por
    defecto, sino `PermissionDeniedError` (403).
    """
    rule = SCOPE_RULES.get(role)
    if rule is None:
        raise PermissionDeniedError()
    return rule(organization_id)
