/**
 * Parte de recursos del backend falso de los tests. Imita el contrato real
 * (permisos, `version` y 409, `resource_inactive`, `resource_code_taken`).
 * Todo es ficticio y solo existe aquí.
 */
import type { components } from "@/types/api"

type Schemas = components["schemas"]
type Resource = Schemas["ResourceResponse"]
type Status = Schemas["ResourceStatus"]
type Me = Schemas["MeResponse"]

export const RESOURCE_TYPES: Schemas["ResourceTypeResponse"][] = [
  {
    id: "40000000-0000-4000-8000-000000000001",
    code: "fire_engine",
    category: "fire",
    icon: "Truck",
    average_speed_kmh: 50,
    is_active: true,
  },
  {
    id: "40000000-0000-4000-8000-000000000002",
    code: "ambulance_basic",
    category: "medical",
    icon: "Ambulance",
    average_speed_kmh: 60,
    is_active: true,
  },
]

const STATUS_RANK: Record<Status, number> = { available: 0, in_service: 1, out_of_service: 2 }

export interface ResourceSeed {
  code: string
  name?: string
  status?: Status
  typeCode?: string
  isActive?: boolean
  /** Coordenadas de la base (latitud, longitud). */
  base?: { latitude: number; longitude: number }
}

export class FakeResources {
  readonly resources: Resource[] = []
  /** Lo fija el doble de asignaciones: asignación activa de cada recurso. */
  currentFor: (resourceId: string) => Resource["current_assignment"] = () => null
  private clock = Date.parse("2026-10-07T07:00:00Z")

  private readonly organization: Schemas["OrganizationSummary"]

  constructor(organization: Schemas["OrganizationSummary"]) {
    this.organization = organization
  }

  add(seed: ResourceSeed): Resource {
    const type = RESOURCE_TYPES.find((t) => t.code === (seed.typeCode ?? "fire_engine"))
    if (!type) throw new Error("tipo desconocido")
    const now = this.now()
    const resource: Resource = {
      id: `50000000-0000-4000-8000-${String(this.resources.length + 1).padStart(12, "0")}`,
      code: seed.code,
      name: seed.name ?? `${seed.code} (simulado)`,
      type,
      organization: this.organization,
      status: seed.status ?? "available",
      status_changed_at: now,
      base: {
        municipality: "Oviedo",
        description: null,
        latitude: seed.base?.latitude ?? null,
        longitude: seed.base?.longitude ?? null,
      },
      current_assignment: null,
      is_active: seed.isActive ?? true,
      is_simulated: true,
      version: 1,
      created_at: now,
      updated_at: now,
    }
    this.resources.push(resource)
    return resource
  }

  byCode(code: string): Resource {
    const resource = this.resources.find((candidate) => candidate.code === code)
    if (!resource) throw new Error(code)
    return resource
  }

  /** Recuento por estado para el resumen del dashboard (como el backend). */
  summary(): Schemas["ResourceKpis"] {
    const active = this.resources.filter((resource) => resource.is_active)
    const byStatus: Record<Status, number> = { available: 0, in_service: 0, out_of_service: 0 }
    for (const resource of active) byStatus[resource.status] += 1
    return {
      active_total: active.length,
      by_status: byStatus,
      inactive_total: this.resources.length - active.length,
    }
  }

  handle(
    method: string,
    path: string,
    query: URLSearchParams,
    user: Me,
    body: BodyInit | null | undefined
  ): Response | null {
    const can = (permission: Schemas["Permission"]) => user.permissions.includes(permission)
    const route = `${method} ${path.replace(/\/resources\/[^/]+/, "/resources/:id")}`
    const id = /^\/resources\/([^/]+)/.exec(path)?.[1]
    const input = typeof body === "string" ? (JSON.parse(body) as Record<string, unknown>) : {}

    if (route === "GET /resource-types") return json(200, RESOURCE_TYPES)
    if (!path.startsWith("/resources")) return null
    if (!can("resources:read")) return error(403, "permission_denied")

    if (route === "GET /resources") return json(200, this.list(query))
    if (route === "POST /resources") {
      if (!can("resources:manage")) return error(403, "permission_denied")
      const code = String(input.code).toUpperCase()
      if (this.resources.some((resource) => resource.code === code))
        return error(409, "resource_code_taken")
      const type = RESOURCE_TYPES.find((candidate) => candidate.id === input.type_id)
      const resource = this.add({ code, name: String(input.name), typeCode: type?.code })
      const base = input.base as Schemas["LocationInput"]
      resource.base = {
        municipality: base.municipality,
        description: base.description ?? null,
        latitude: base.latitude ?? null,
        longitude: base.longitude ?? null,
      }
      resource.is_simulated = false
      if (typeof input.status === "string") resource.status = input.status as Status
      return json(201, this.view(resource))
    }

    const resource = this.resources.find((candidate) => candidate.id === id)
    if (!resource) return error(404, "resource_not_found")
    if (route === "GET /resources/:id") return json(200, this.view(resource))

    if (route === "POST /resources/:id/status") {
      if (!can("resources:update_status")) return error(403, "permission_denied")
      if (input.version !== resource.version) return error(409, "version_conflict")
      if (!resource.is_active) return error(422, "resource_inactive")
      if (input.status === resource.status) return error(422, "invalid_transition")
      if (this.currentFor(resource.id)) return error(422, "resource_assigned")
      resource.status = input.status as Status
      resource.status_changed_at = this.now()
      resource.version += 1
      return json(200, this.view(resource))
    }
    if (route === "PATCH /resources/:id") {
      if (!can("resources:manage")) return error(403, "permission_denied")
      if (input.version !== resource.version) return error(409, "version_conflict")
      let changed = false
      if (input.is_active === false && this.currentFor(resource.id))
        return error(422, "resource_assigned")
      if (input.base) {
        resource.base = { ...resource.base, ...(input.base as Schemas["LocationInput"]) }
        changed = true
      }
      for (const field of ["name", "is_active"] as const) {
        if (field in input && input[field] !== resource[field]) {
          Object.assign(resource, { [field]: input[field] })
          changed = true
        }
      }
      if (changed) resource.version += 1
      return json(200, this.view(resource))
    }
    return error(404, "not_found")
  }

  private view(resource: Resource): Resource {
    return { ...resource, current_assignment: this.currentFor(resource.id) }
  }

  private now(): string {
    this.clock += 60_000
    return new Date(this.clock).toISOString()
  }

  private list(query: URLSearchParams): Schemas["ResourcePage"] {
    const statuses = query.getAll("status")
    const type = query.get("type")
    const q = query.get("q")?.toLowerCase()
    const limit = Number(query.get("limit") ?? 50)
    const offset = Number(query.get("offset") ?? 0)
    const sort = query.get("sort") ?? "code"
    const filtered = this.resources
      .filter((resource) => query.get("active") === "false" || resource.is_active)
      .filter((resource) => statuses.length === 0 || statuses.includes(resource.status))
      .filter((resource) => !type || resource.type.code === type)
      .filter(
        (resource) =>
          !q || resource.code.toLowerCase().includes(q) || resource.name.toLowerCase().includes(q)
      )
      .sort((a, b) =>
        sort === "status"
          ? STATUS_RANK[a.status] - STATUS_RANK[b.status] || a.code.localeCompare(b.code)
          : a.code.localeCompare(b.code)
      )
    return {
      items: filtered.slice(offset, offset + limit).map((resource) => this.view(resource)),
      total: filtered.length,
      limit,
      offset,
    }
  }
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

function error(status: number, detail: string): Response {
  return json(status, { detail })
}
