/**
 * Parte de incidentes del backend falso de los tests. Imita el contrato real
 * (códigos de error, `version` y 409, `allowed_transitions`, historial). Todo
 * es ficticio y solo existe aquí.
 */
import type { components } from "@/types/api"

type Schemas = components["schemas"]
type Status = Schemas["IncidentStatus"]
type Priority = Schemas["IncidentPriority"]
type Detail = Schemas["IncidentDetail"]
type Event = Schemas["IncidentEventResponse"]
type Me = Schemas["MeResponse"]

export const INCIDENT_TYPES: Schemas["IncidentTypeResponse"][] = [
  {
    id: "10000000-0000-4000-8000-000000000001",
    code: "wildfire",
    category: "fire",
    icon: "Flame",
    default_priority: "high",
    suggested_resource_types: ["fire_engine"],
    common_risks: ["fire_spread"],
    details_schema_key: "wildfire",
    is_active: true,
  },
  {
    id: "10000000-0000-4000-8000-000000000002",
    code: "traffic_accident",
    category: "traffic",
    icon: "CarFront",
    default_priority: "medium",
    suggested_resource_types: ["ambulance_basic"],
    common_risks: ["trapped_people"],
    details_schema_key: null,
    is_active: true,
  },
]

// Copia de prueba del flujo del backend (domain/incident_rules.py).
const TRANSITIONS: Record<Status, Status[]> = {
  received: ["assessing", "cancelled"],
  assessing: ["in_progress", "cancelled"],
  resources_assigned: [],
  in_progress: ["controlled", "cancelled"],
  controlled: ["in_progress", "closed"],
  closed: [],
  cancelled: [],
}
const TERMINAL: Status[] = ["closed", "cancelled"]
const RANK: Record<Priority, number> = { critical: 0, high: 1, medium: 2, low: 3 }
const CLOSING: Status[] = ["closed", "cancelled"]

type Stored = Omit<Detail, "allowed_transitions" | "children" | "parent">

export interface IncidentSeed {
  title: string
  priority?: Priority
  status?: Status
  typeCode?: string
  parentCode?: string
  isSimulated?: boolean
  coordinates?: { latitude: number; longitude: number }
}

export class FakeIncidents {
  readonly incidents: Stored[] = []
  private readonly events = new Map<string, Event[]>()
  /** El listado responde 500. */
  failList = false
  private sequence = 0
  private clock = Date.parse("2026-10-07T08:00:00Z")

  /** Crea un incidente directamente en el «servidor» (datos previos de un test). */
  add(seed: IncidentSeed): Detail {
    const type = INCIDENT_TYPES.find((t) => t.code === (seed.typeCode ?? "traffic_accident"))
    if (!type) throw new Error("tipo desconocido")
    const parent = seed.parentCode ? this.byCode(seed.parentCode) : undefined
    const stored = this.insert(
      {
        type_id: type.id,
        title: seed.title,
        priority: seed.priority ?? type.default_priority,
        location: { municipality: "Oviedo", ...seed.coordinates },
        parent_incident_id: parent?.id ?? null,
      },
      null,
      seed.isSimulated ?? true
    )
    if (seed.status) stored.status = seed.status
    if (seed.status && TERMINAL.includes(seed.status)) stored.closed_at = this.now()
    return this.detail(stored)
  }

  byCode(code: string): Stored {
    const incident = this.incidents.find((candidate) => candidate.code === code)
    if (!incident) throw new Error(code)
    return incident
  }

  /** Simula que otra persona modifica el incidente (su `version` avanza). */
  touch(code: string): void {
    this.byCode(code).version += 1
  }

  /** KPIs de incidentes para el resumen del dashboard (como el backend). */
  summary(): Schemas["IncidentKpis"] {
    const active = this.incidents.filter((incident) => !TERMINAL.includes(incident.status))
    const byPriority: Record<Priority, number> = { critical: 0, high: 0, medium: 0, low: 0 }
    const byStatus: Partial<Record<Status, number>> = {}
    for (const status of Object.keys(TRANSITIONS) as Status[]) {
      if (!TERMINAL.includes(status)) byStatus[status] = 0
    }
    for (const incident of active) {
      byPriority[incident.priority] += 1
      byStatus[incident.status] = (byStatus[incident.status] ?? 0) + 1
    }
    return {
      active_total: active.length,
      by_priority: byPriority,
      by_status: byStatus,
      affected_people: active.reduce((sum, incident) => sum + (incident.affected_people ?? 0), 0),
      reported_last_24h: this.incidents.length,
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
    const route = `${method} ${path.replace(/\/incidents\/[^/]+/, "/incidents/:id")}`
    const id = /^\/incidents\/([^/]+)/.exec(path)?.[1]
    const input = typeof body === "string" ? (JSON.parse(body) as Record<string, unknown>) : {}

    if (route === "GET /incident-types") return json(200, INCIDENT_TYPES)
    if (!path.startsWith("/incidents")) return null
    if (!can("incidents:read")) return error(403, "permission_denied")

    if (route === "GET /incidents") {
      if (this.failList) return error(500, "internal_error")
      return json(200, this.list(query))
    }
    if (route === "POST /incidents") {
      if (!can("incidents:create")) return error(403, "permission_denied")
      const stored = this.insert(input as unknown as Schemas["IncidentCreate"], user, false)
      return json(201, this.detail(stored))
    }

    const incident = this.incidents.find((candidate) => candidate.id === id)
    if (!incident) return error(404, "incident_not_found")

    if (route === "GET /incidents/:id") return json(200, this.detail(incident))
    if (route === "GET /incidents/:id/events") return json(200, this.events.get(incident.id) ?? [])

    if (!can("incidents:update")) return error(403, "permission_denied")

    if (route === "POST /incidents/:id/notes") {
      const event = this.record(incident, user, "note_added", { text: input.text })
      return json(201, event)
    }
    if (input.version !== incident.version) return error(409, "version_conflict")

    if (route === "POST /incidents/:id/status") {
      const target = input.status as Status
      if (!TRANSITIONS[incident.status].includes(target)) return error(422, "invalid_transition")
      if (CLOSING.includes(target) && !can("incidents:close"))
        return error(403, "permission_denied")
      const payload: Record<string, unknown> = { from: incident.status, to: target }
      if (typeof input.reason === "string") payload.reason = input.reason
      incident.status = target
      incident.closed_at = TERMINAL.includes(target) ? this.now() : null
      incident.version += 1
      this.record(incident, user, "status_changed", payload)
      return json(200, this.detail(incident))
    }
    if (route === "PATCH /incidents/:id") {
      if (TERMINAL.includes(incident.status)) return error(422, "incident_closed")
      const changed: string[] = []
      for (const field of ["title", "description", "affected_people"] as const) {
        if (field in input && input[field] !== incident[field]) {
          Object.assign(incident, { [field]: input[field] })
          changed.push(field)
        }
      }
      // Como el backend: la ubicación se sustituye completa y sus cambios van
      // en un `location_changed` propio, con el antes y el después.
      if (input.location) {
        const sent = input.location as Schemas["LocationInput"]
        const next: Schemas["LocationResponse"] = {
          municipality: sent.municipality,
          description: sent.description === "" ? null : (sent.description ?? null),
          latitude: sent.latitude ?? null,
          longitude: sent.longitude ?? null,
        }
        const before = incident.location
        const fields = (["municipality", "description"] as const).filter(
          (field) => next[field] !== before[field]
        ) as string[]
        if (next.latitude !== before.latitude || next.longitude !== before.longitude)
          fields.push("coordinates")
        if (fields.length > 0) {
          this.record(incident, user, "location_changed", {
            fields: fields.sort(),
            from: before,
            to: next,
          })
          incident.location = next
        }
      }
      if (typeof input.priority === "string" && input.priority !== incident.priority) {
        this.record(incident, user, "priority_changed", {
          from: incident.priority,
          to: input.priority,
        })
        incident.priority = input.priority as Priority
      }
      if (changed.length > 0) this.record(incident, user, "incident_updated", { fields: changed })
      incident.version += 1
      return json(200, this.detail(incident))
    }
    return error(404, "not_found")
  }

  // --- Internos ---------------------------------------------------------------

  private now(): string {
    this.clock += 60_000
    return new Date(this.clock).toISOString()
  }

  private insert(
    data: Pick<
      Schemas["IncidentCreate"],
      "type_id" | "title" | "priority" | "location" | "parent_incident_id"
    > &
      Partial<Schemas["IncidentCreate"]>,
    user: Me | null,
    isSimulated: boolean
  ): Stored {
    const type = INCIDENT_TYPES.find((candidate) => candidate.id === data.type_id)
    if (!type) throw new Error("tipo desconocido")
    const number = ++this.sequence
    const now = this.now()
    const stored: Stored = {
      id: `20000000-0000-4000-8000-${String(number).padStart(12, "0")}`,
      code: `INC-${String(number).padStart(6, "0")}`,
      title: data.title,
      status: "received",
      priority: data.priority ?? type.default_priority,
      type: { id: type.id, code: type.code, category: type.category, icon: type.icon },
      location: {
        municipality: data.location.municipality,
        description: data.location.description ?? null,
        latitude: data.location.latitude ?? null,
        longitude: data.location.longitude ?? null,
      },
      affected_people: data.affected_people ?? null,
      parent_incident_id: data.parent_incident_id ?? null,
      is_simulated: isSimulated,
      version: 1,
      reported_at: now,
      updated_at: now,
      description: data.description ?? null,
      details: data.details ?? {},
      closed_at: null,
      created_at: now,
    }
    this.incidents.push(stored)
    this.record(stored, user, "incident_created", {
      status: "received",
      priority: stored.priority,
      type: type.code,
      parent: null,
    })
    return stored
  }

  private record(
    incident: Stored,
    user: Me | null,
    eventType: Event["event_type"],
    payload: Record<string, unknown>
  ): Event {
    const events = this.events.get(incident.id) ?? []
    const event: Event = {
      id: `30000000-0000-4000-8000-${String(events.length + 1).padStart(12, "0")}`,
      event_type: eventType,
      occurred_at: this.now(),
      actor: user ? { id: user.id, full_name: user.full_name } : null,
      payload,
      is_simulated: incident.is_simulated,
    }
    this.events.set(incident.id, [...events, event])
    incident.updated_at = event.occurred_at
    return event
  }

  private ref(incident: Stored): Schemas["IncidentRef"] {
    const { id, code, title, status, priority } = incident
    return { id, code, title, status, priority }
  }

  private detail(incident: Stored): Detail {
    const parent = this.incidents.find((candidate) => candidate.id === incident.parent_incident_id)
    return {
      ...incident,
      parent: parent ? this.ref(parent) : null,
      children: this.incidents
        .filter((candidate) => candidate.parent_incident_id === incident.id)
        .map((child) => this.ref(child)),
      allowed_transitions: TRANSITIONS[incident.status],
    }
  }

  private list(query: URLSearchParams): Schemas["IncidentPage"] {
    const statuses = query.getAll("status")
    const priorities = query.getAll("priority")
    const type = query.get("type")
    const q = query.get("q")?.toLowerCase()
    const limit = Number(query.get("limit") ?? 50)
    const offset = Number(query.get("offset") ?? 0)
    const filtered = this.incidents
      .filter((incident) => query.get("active") === "false" || !TERMINAL.includes(incident.status))
      .filter((incident) => statuses.length === 0 || statuses.includes(incident.status))
      .filter((incident) => priorities.length === 0 || priorities.includes(incident.priority))
      .filter((incident) => !type || incident.type.code === type)
      .filter(
        (incident) =>
          !q || incident.code.toLowerCase().includes(q) || incident.title.toLowerCase().includes(q)
      )
      .sort(
        (a, b) => RANK[a.priority] - RANK[b.priority] || b.reported_at.localeCompare(a.reported_at)
      )
    return {
      items: filtered.slice(offset, offset + limit),
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
