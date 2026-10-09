import type { IncidentDetail } from "@/features/incidents/types"
import { apiRequest } from "@/lib/api-client"
import { toQueryString } from "@/lib/query-string"

import type {
  Assignment,
  AssignmentCandidate,
  AssignmentCreate,
  AssignmentRelease,
  CandidateParams,
} from "./types"

const incidentPath = (id: string) => `/incidents/${encodeURIComponent(id)}`
const assignmentPath = (id: string) => `/assignments/${encodeURIComponent(id)}`

export function fetchAssignments(incidentId: string, signal?: AbortSignal): Promise<Assignment[]> {
  return apiRequest<Assignment[]>(`${incidentPath(incidentId)}/assignments`, { signal })
}

/** Candidatos ordenados por ETA estimada. Ayuda a la decisión: nada se preselecciona. */
export function fetchCandidates(
  incidentId: string,
  params: CandidateParams,
  signal?: AbortSignal
): Promise<AssignmentCandidate[]> {
  return apiRequest<AssignmentCandidate[]>(
    `${incidentPath(incidentId)}/assignment-candidates${toQueryString(params)}`,
    { signal }
  )
}

export function assignResource(
  incidentId: string,
  body: AssignmentCreate
): Promise<IncidentDetail> {
  return apiRequest<IncidentDetail>(`${incidentPath(incidentId)}/assignments`, {
    method: "POST",
    body,
  })
}

export function markArrival(assignmentId: string, version: number): Promise<IncidentDetail> {
  return apiRequest<IncidentDetail>(`${assignmentPath(assignmentId)}/arrival`, {
    method: "POST",
    body: { version },
  })
}

export function releaseResource(
  assignmentId: string,
  body: AssignmentRelease
): Promise<IncidentDetail> {
  return apiRequest<IncidentDetail>(`${assignmentPath(assignmentId)}/release`, {
    method: "POST",
    body,
  })
}
