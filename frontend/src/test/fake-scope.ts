/**
 * Ámbito organizativo del backend falso: mismas reglas que `scope_for`
 * (app/domain/access_scope.py, CLAUDE.md §2.11, D1, D3 y D4).
 */
import type { components } from "@/types/api"

type Schemas = components["schemas"]
type Me = Schemas["MeResponse"]

const ALL: Me["scope"]["read"] = { all_organizations: true, organization_ids: [] }

/** Mismas reglas que `scope_for` (app/domain/access_scope.py, D1, D3 y D4). */
export function scopeFor(
  role: Me["role"],
  organization: Schemas["OrganizationSummary"] | null
): Me["scope"] {
  if (role !== "operator") return { read: ALL, write: ALL }
  return {
    read: ALL,
    write: { all_organizations: false, organization_ids: organization ? [organization.id] : [] },
  }
}

/** ¿Puede el usuario modificar recursos de esta organización? (como el backend) */
export function canWrite(user: Me, organizationId: string): boolean {
  const { write } = user.scope
  return write.all_organizations || write.organization_ids.includes(organizationId)
}
