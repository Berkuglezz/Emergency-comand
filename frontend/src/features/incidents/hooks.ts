import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { queryKeys } from "@/lib/query-keys"

import {
  addIncidentNote,
  changeIncidentStatus,
  createIncident,
  fetchIncident,
  fetchIncidentEvents,
  fetchIncidentMap,
  fetchIncidents,
  fetchIncidentTypes,
  updateIncident,
} from "./api"
import type {
  IncidentCreate,
  IncidentDetail,
  IncidentListParams,
  IncidentMapParams,
  IncidentNoteCreate,
  IncidentStatusChange,
  IncidentUpdate,
} from "./types"

/** Catálogo de tipos: datos de referencia que casi nunca cambian. */
export function useIncidentTypes() {
  return useQuery({
    queryKey: queryKeys.incidentTypes,
    queryFn: ({ signal }) => fetchIncidentTypes(signal),
    staleTime: 10 * 60_000,
  })
}

export function useIncidents(params: IncidentListParams) {
  return useQuery({
    queryKey: queryKeys.incidentList(params),
    queryFn: ({ signal }) => fetchIncidents(params, signal),
    // Al cambiar de página o filtro se mantiene la tabla anterior hasta que llega la nueva.
    placeholderData: keepPreviousData,
  })
}

export function useIncidentMap(params: IncidentMapParams) {
  return useQuery({
    queryKey: queryKeys.incidentMap(params),
    queryFn: ({ signal }) => fetchIncidentMap(params, signal),
    // Al cambiar un filtro los marcadores anteriores se mantienen hasta que llegan los nuevos.
    placeholderData: keepPreviousData,
  })
}

export function useIncident(id: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.incident(id),
    queryFn: ({ signal }) => fetchIncident(id, signal),
    enabled: options.enabled,
  })
}

export function useIncidentEvents(id: string) {
  return useQuery({
    queryKey: queryKeys.incidentEvents(id),
    queryFn: ({ signal }) => fetchIncidentEvents(id, signal),
  })
}

/** Tras escribir: el detalle se actualiza con la respuesta y se refresca lo demás
 * (listados, historial y KPIs), que el servidor ha cambiado en la misma transacción. */
function useApplyIncident() {
  const queryClient = useQueryClient()
  return (incident: IncidentDetail) => {
    queryClient.setQueryData(queryKeys.incident(incident.id), incident)
    void queryClient.invalidateQueries({ queryKey: queryKeys.incidents })
    // Los KPIs del centro de mando dependen de estados y prioridades.
    void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard })
    // Cerrar o cancelar retira los recursos asignados: cambia su estado.
    void queryClient.invalidateQueries({ queryKey: queryKeys.resources })
  }
}

export function useCreateIncident() {
  const apply = useApplyIncident()
  return useMutation({
    mutationFn: (body: IncidentCreate) => createIncident(body),
    onSuccess: apply,
  })
}

export function useUpdateIncident(id: string) {
  const apply = useApplyIncident()
  return useMutation({
    mutationFn: (body: IncidentUpdate) => updateIncident(id, body),
    onSuccess: apply,
  })
}

export function useChangeIncidentStatus(id: string) {
  const apply = useApplyIncident()
  return useMutation({
    mutationFn: (body: IncidentStatusChange) => changeIncidentStatus(id, body),
    onSuccess: apply,
  })
}

export function useAddIncidentNote(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: IncidentNoteCreate) => addIncidentNote(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.incidentEvents(id) })
    },
  })
}
