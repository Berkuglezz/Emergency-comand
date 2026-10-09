/**
 * Asignaciones del backend falso de los tests. Imita el contrato real (CLAUDE.md
 * §2.8): permisos, `version` y 409, un recurso con una sola asignación activa,
 * cambios automáticos de estado, retirada al cerrar y ETA estimada guardada al
 * asignar. La ETA usa la misma fórmula que el backend. Todo es ficticio.
 */
import type { components } from "@/types/api"

import type { FakeIncidents, StoredIncident } from "./fake-incidents"
import type { FakeResources } from "./fake-resources"
import { canWrite } from "./fake-scope"

type Schemas = components["schemas"]
type Me = Schemas["MeResponse"]
type Assignment = Schemas["AssignmentResponse"]
type Resource = Schemas["ResourceResponse"]
type Reason = Schemas["ReleaseReason"]

const USER_REASONS: Reason[] = ["completed", "not_needed", "unavailable"]
const TERMINAL = ["closed", "cancelled"]
const SPEED_KMH: Record<string, number> = { fire_engine: 50, ambulance_basic: 60 }

function haversineKm([lat1, lon1]: [number, number], [lat2, lon2]: [number, number]): number {
  const rad = (value: number) => (value * Math.PI) / 180
  const h =
    Math.sin(rad(lat2 - lat1) / 2) ** 2 +
    Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2
  return 2 * 6371.0088 * Math.asin(Math.sqrt(h))
}

export class FakeAssignments {
  readonly assignments: Assignment[] = []
  /** La próxima escritura responde `409 concurrent_update` (PostgreSQL abortó la transacción). */
  abortNextWrite = false

  private readonly incidents: FakeIncidents
  private readonly resources: FakeResources

  constructor(incidents: FakeIncidents, resources: FakeResources) {
    this.incidents = incidents
    this.resources = resources
    resources.currentFor = (resourceId) => this.currentFor(resourceId)
    incidents.onClose = (incident, user) => {
      for (const assignment of this.active(incident.id)) {
        this.release(assignment, incident, "incident_closed", user, false)
      }
    }
  }

  /** Asigna directamente (datos previos de un test), con las mismas reglas. */
  assign(incidentCode: string, resourceCode: string): Assignment {
    const incident = this.incidents.byCode(incidentCode)
    const resource = this.resources.byCode(resourceCode)
    return this.create(incident, resource, null, null)
  }

  handle(
    method: string,
    path: string,
    query: URLSearchParams,
    user: Me,
    body: BodyInit | null | undefined
  ): Response | null {
    const can = (permission: Schemas["Permission"]) => user.permissions.includes(permission)
    const input = typeof body === "string" ? (JSON.parse(body) as Record<string, unknown>) : {}

    if (method === "POST" && this.abortNextWrite && path.includes("assignments")) {
      this.abortNextWrite = false
      return error(409, "concurrent_update")
    }
    const byIncident = /^\/incidents\/([^/]+)\/(assignments|assignment-candidates)$/.exec(path)
    if (byIncident) {
      const [, incidentId, kind] = byIncident
      if (!can("incidents:read")) return error(403, "permission_denied")
      const incident = this.incidents.incidents.find((candidate) => candidate.id === incidentId)
      if (!incident) return error(404, "incident_not_found")
      if (method === "GET" && kind === "assignments") {
        const list = this.assignments.filter((a) => a.incident_id === incident.id)
        return json(200, [
          ...list.filter((a) => a.released_at === null),
          ...list.filter((a) => a.released_at !== null),
        ])
      }
      if (method === "GET") {
        if (!can("resources:read")) return error(403, "permission_denied")
        return json(200, this.candidates(incident, query, user))
      }
      if (!can("assignments:manage")) return error(403, "permission_denied")
      if (input.version !== incident.version) return error(409, "version_conflict")
      if (TERMINAL.includes(incident.status)) return error(422, "incident_closed")
      const resource = this.resources.resources.find((r) => r.id === input.resource_id)
      if (!resource) return error(404, "resource_not_found")
      if (!canWrite(user, resource.organization.id)) return error(403, "organization_out_of_scope")
      const current = this.activeFor(resource.id)
      let from: string | null = null
      if (current) {
        if (current.incident_id === incident.id || input.reassign !== true)
          return error(409, "resource_already_assigned")
        const origin = this.incidentById(current.incident_id)
        this.release(current, origin, "reassigned", user, true, incident.code)
        origin.version += 1
        from = origin.code
      } else if (!resource.is_active) {
        return error(422, "resource_inactive")
      } else if (resource.status !== "available") {
        return error(422, "resource_not_available")
      }
      this.create(incident, resource, user, from)
      incident.version += 1
      return json(200, this.incidents.detail(incident))
    }

    const byAssignment = /^\/assignments\/([^/]+)\/(arrival|release)$/.exec(path)
    if (byAssignment && method === "POST") {
      const [, assignmentId, action] = byAssignment
      const permission = action === "arrival" ? "assignments:update" : "assignments:manage"
      if (!can(permission)) return error(403, "permission_denied")
      const assignment = this.assignments.find((a) => a.id === assignmentId)
      if (!assignment) return error(404, "assignment_not_found")
      if (action === "release" && !USER_REASONS.includes(input.reason as Reason))
        return error(422, "invalid_release_reason")
      const incident = this.incidentById(assignment.incident_id)
      if (input.version !== incident.version) return error(409, "version_conflict")
      if (assignment.released_at !== null) return error(422, "assignment_already_released")
      if (!canWrite(user, assignment.resource.organization.id))
        return error(403, "organization_out_of_scope")
      if (action === "arrival") {
        if (assignment.arrived_at !== null) return error(422, "assignment_already_arrived")
        assignment.arrived_at = this.incidents.now()
        this.incidents.record(incident, user, "resource_arrived", {
          resource: assignment.resource.code,
          resource_id: assignment.resource.id,
        })
      } else {
        this.release(assignment, incident, input.reason as Reason, user, true)
      }
      incident.version += 1
      return json(200, this.incidents.detail(incident))
    }
    return null
  }

  /** Asignación activa de un recurso, para `current_assignment` del doble de recursos. */
  currentFor(resourceId: string): Schemas["CurrentAssignment"] | null {
    const assignment = this.activeFor(resourceId)
    if (!assignment) return null
    return {
      id: assignment.id,
      incident_id: assignment.incident_id,
      incident_code: this.incidentById(assignment.incident_id).code,
      assigned_at: assignment.assigned_at,
      arrived_at: assignment.arrived_at,
      eta: assignment.eta,
    }
  }

  // --- Internos ---------------------------------------------------------------

  private create(
    incident: StoredIncident,
    resource: Resource,
    user: Me | null,
    reassignedFrom: string | null
  ): Assignment {
    const eta = this.eta(resource, incident)
    const assignment: Assignment = {
      id: `60000000-0000-4000-8000-${String(this.assignments.length + 1).padStart(12, "0")}`,
      incident_id: incident.id,
      resource: {
        id: resource.id,
        code: resource.code,
        name: resource.name,
        status: "in_service",
        type: resource.type,
        organization: resource.organization,
        base: resource.base,
        is_simulated: resource.is_simulated,
      },
      assigned_at: this.incidents.now(),
      arrived_at: null,
      released_at: null,
      release_reason: null,
      eta,
      is_simulated: incident.is_simulated,
    }
    this.assignments.push(assignment)
    resource.status = "in_service"
    resource.version += 1
    this.incidents.record(incident, user, "resource_assigned", {
      resource: resource.code,
      resource_id: resource.id,
      resource_type: resource.type.code,
      eta,
      eta_unavailable: eta ? null : "incident_without_coordinates",
      reassigned_from: reassignedFrom,
    })
    if (incident.status === "received" || incident.status === "assessing") {
      this.incidents.record(incident, user, "status_changed", {
        from: incident.status,
        to: "resources_assigned",
        cause: "assignment",
      })
      incident.status = "resources_assigned"
    }
    incident.active_assignments = this.active(incident.id).length
    return assignment
  }

  private release(
    assignment: Assignment,
    incident: StoredIncident,
    reason: Reason,
    user: Me,
    applyStatusRule: boolean,
    reassignedTo: string | null = null
  ): void {
    assignment.released_at = this.incidents.now()
    assignment.release_reason = reason
    const resource = this.resources.resources.find((r) => r.id === assignment.resource.id)
    if (resource) {
      resource.status = reason === "unavailable" ? "out_of_service" : "available"
      resource.version += 1
    }
    this.incidents.record(incident, user, "resource_released", {
      resource: assignment.resource.code,
      resource_id: assignment.resource.id,
      reason,
      reassigned_to: reassignedTo,
    })
    incident.active_assignments = this.active(incident.id).length
    if (
      applyStatusRule &&
      incident.active_assignments === 0 &&
      incident.status === "resources_assigned"
    ) {
      this.incidents.record(incident, user, "status_changed", {
        from: incident.status,
        to: "assessing",
        cause: "assignment",
      })
      incident.status = "assessing"
    }
  }

  private candidates(
    incident: StoredIncident,
    query: URLSearchParams,
    user: Me
  ): Schemas["AssignmentCandidate"][] {
    const type = query.get("type")
    const includeAssigned = query.get("include_assigned") === "true"
    const suggested = this.incidents.typeOf(incident).suggested_resource_types
    const list: Schemas["AssignmentCandidate"][] = []
    for (const resource of this.resources.resources) {
      if (!resource.is_active || (type && resource.type.code !== type)) continue
      // Solo los del ámbito de escritura: los que el usuario podría asignar.
      if (!canWrite(user, resource.organization.id)) continue
      const current = this.activeFor(resource.id)
      if (current && (current.incident_id === incident.id || !includeAssigned)) continue
      if (!current && resource.status !== "available") continue
      const eta = this.eta(resource, incident)
      list.push({
        resource: { ...resource, is_simulated: resource.is_simulated },
        eta,
        eta_unavailable: eta
          ? null
          : incident.location.latitude === null
            ? "incident_without_coordinates"
            : "resource_without_position",
        suggested: suggested.includes(resource.type.code),
        current_incident: current
          ? { id: current.incident_id, code: this.incidentById(current.incident_id).code }
          : null,
      })
    }
    return list.sort(
      (a, b) =>
        Number(a.eta === null) - Number(b.eta === null) ||
        (a.eta?.minutes ?? 0) - (b.eta?.minutes ?? 0) ||
        a.resource.code.localeCompare(b.resource.code)
    )
  }

  private eta(resource: Resource, incident: StoredIncident): Schemas["EtaResponse"] | null {
    const { latitude: lat1, longitude: lon1 } = resource.base
    const { latitude: lat2, longitude: lon2 } = incident.location
    if (lat1 === null || lon1 === null || lat2 === null || lon2 === null) return null
    const distance = haversineKm([lat1, lon1], [lat2, lon2]) * 1.4
    const speed = SPEED_KMH[resource.type.code] ?? 50
    return {
      minutes: Math.ceil((distance / speed) * 60),
      distance_km: Math.round(distance * 10) / 10,
      origin: "base",
    }
  }

  private active(incidentId: string): Assignment[] {
    return this.assignments.filter((a) => a.incident_id === incidentId && a.released_at === null)
  }

  private activeFor(resourceId: string): Assignment | undefined {
    return this.assignments.find((a) => a.resource.id === resourceId && a.released_at === null)
  }

  private incidentById(id: string): StoredIncident {
    const incident = this.incidents.incidents.find((candidate) => candidate.id === id)
    if (!incident) throw new Error(id)
    return incident
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
