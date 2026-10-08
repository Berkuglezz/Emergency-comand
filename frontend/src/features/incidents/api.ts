import { apiRequest } from "@/lib/api-client"
import { toQueryString } from "@/lib/query-string"

import type {
  IncidentCreate,
  IncidentDetail,
  IncidentEvent,
  IncidentListParams,
  IncidentMapCollection,
  IncidentMapParams,
  IncidentNoteCreate,
  IncidentPage,
  IncidentStatusChange,
  IncidentType,
  IncidentUpdate,
} from "./types"

export function fetchIncidentTypes(signal?: AbortSignal): Promise<IncidentType[]> {
  return apiRequest<IncidentType[]>("/incident-types", { signal })
}

export function fetchIncidents(
  params: IncidentListParams,
  signal?: AbortSignal
): Promise<IncidentPage> {
  return apiRequest<IncidentPage>(`/incidents${toQueryString(params)}`, { signal })
}

/** Incidentes con coordenadas (GeoJSON) para el mapa. No sustituye al listado. */
export function fetchIncidentMap(
  params: IncidentMapParams,
  signal?: AbortSignal
): Promise<IncidentMapCollection> {
  return apiRequest<IncidentMapCollection>(`/incidents/map${toQueryString(params)}`, { signal })
}

export function fetchIncident(id: string, signal?: AbortSignal): Promise<IncidentDetail> {
  return apiRequest<IncidentDetail>(`/incidents/${encodeURIComponent(id)}`, { signal })
}

export function fetchIncidentEvents(id: string, signal?: AbortSignal): Promise<IncidentEvent[]> {
  return apiRequest<IncidentEvent[]>(`/incidents/${encodeURIComponent(id)}/events`, { signal })
}

export function createIncident(body: IncidentCreate): Promise<IncidentDetail> {
  return apiRequest<IncidentDetail>("/incidents", { method: "POST", body })
}

export function updateIncident(id: string, body: IncidentUpdate): Promise<IncidentDetail> {
  return apiRequest<IncidentDetail>(`/incidents/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body,
  })
}

export function changeIncidentStatus(
  id: string,
  body: IncidentStatusChange
): Promise<IncidentDetail> {
  return apiRequest<IncidentDetail>(`/incidents/${encodeURIComponent(id)}/status`, {
    method: "POST",
    body,
  })
}

export function addIncidentNote(id: string, body: IncidentNoteCreate): Promise<IncidentEvent> {
  return apiRequest<IncidentEvent>(`/incidents/${encodeURIComponent(id)}/notes`, {
    method: "POST",
    body,
  })
}
