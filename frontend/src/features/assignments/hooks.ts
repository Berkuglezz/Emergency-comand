import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import type { IncidentDetail } from "@/features/incidents/types"
import { queryKeys } from "@/lib/query-keys"

import {
  assignResource,
  fetchAssignments,
  fetchCandidates,
  markArrival,
  releaseResource,
} from "./api"
import type { AssignmentCreate, AssignmentRelease, CandidateParams } from "./types"

export function useAssignments(incidentId: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.incidentAssignments(incidentId),
    queryFn: ({ signal }) => fetchAssignments(incidentId, signal),
    enabled: options.enabled,
  })
}

export function useAssignmentCandidates(
  incidentId: string,
  params: CandidateParams,
  options: { enabled?: boolean } = {}
) {
  return useQuery({
    queryKey: queryKeys.assignmentCandidates(incidentId, params),
    queryFn: ({ signal }) => fetchCandidates(incidentId, params, signal),
    placeholderData: keepPreviousData,
    enabled: options.enabled,
  })
}

/** Tras asignar, marcar la llegada o retirar: el detalle se actualiza con la
 * respuesta y se refresca lo demás (asignaciones, historial, listados, mapa,
 * recursos y KPIs), que el servidor ha cambiado en la misma transacción. Una
 * reasignación cambia también otro incidente: se invalidan todos. */
function useApplyAssignment() {
  const queryClient = useQueryClient()
  return (incident: IncidentDetail) => {
    queryClient.setQueryData(queryKeys.incident(incident.id), incident)
    for (const queryKey of [queryKeys.incidents, queryKeys.resources, queryKeys.dashboard]) {
      void queryClient.invalidateQueries({ queryKey })
    }
  }
}

export function useAssignResource(incidentId: string) {
  const apply = useApplyAssignment()
  return useMutation({
    mutationFn: (body: AssignmentCreate) => assignResource(incidentId, body),
    onSuccess: apply,
  })
}

export function useMarkArrival() {
  const apply = useApplyAssignment()
  return useMutation({
    mutationFn: ({ assignmentId, version }: { assignmentId: string; version: number }) =>
      markArrival(assignmentId, version),
    onSuccess: apply,
  })
}

export function useReleaseResource() {
  const apply = useApplyAssignment()
  return useMutation({
    mutationFn: ({ assignmentId, body }: { assignmentId: string; body: AssignmentRelease }) =>
      releaseResource(assignmentId, body),
    onSuccess: apply,
  })
}
