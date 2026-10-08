import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { queryKeys } from "@/lib/query-keys"

import {
  changeResourceStatus,
  createResource,
  fetchResource,
  fetchResources,
  fetchResourceTypes,
  updateResource,
} from "./api"
import type {
  Resource,
  ResourceCreate,
  ResourceListParams,
  ResourceStatusChange,
  ResourceUpdate,
} from "./types"

/** Catálogo de tipos: datos de referencia que casi nunca cambian. */
export function useResourceTypes({ enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.resourceTypes,
    queryFn: ({ signal }) => fetchResourceTypes(signal),
    staleTime: 10 * 60_000,
    enabled,
  })
}

export function useResources(params: ResourceListParams) {
  return useQuery({
    queryKey: queryKeys.resourceList(params),
    queryFn: ({ signal }) => fetchResources(params, signal),
    placeholderData: keepPreviousData,
  })
}

export function useResource(id: string) {
  return useQuery({
    queryKey: queryKeys.resource(id),
    queryFn: ({ signal }) => fetchResource(id, signal),
  })
}

/** Tras escribir: la ficha se actualiza con la respuesta y se refrescan los
 * listados y los KPIs del centro de mando. */
function useApplyResource() {
  const queryClient = useQueryClient()
  return (resource: Resource) => {
    queryClient.setQueryData(queryKeys.resource(resource.id), resource)
    void queryClient.invalidateQueries({ queryKey: queryKeys.resources })
    void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard })
  }
}

export function useCreateResource() {
  const apply = useApplyResource()
  return useMutation({
    mutationFn: (body: ResourceCreate) => createResource(body),
    onSuccess: apply,
  })
}

export function useUpdateResource(id: string) {
  const apply = useApplyResource()
  return useMutation({
    mutationFn: (body: ResourceUpdate) => updateResource(id, body),
    onSuccess: apply,
  })
}

export function useChangeResourceStatus(id: string) {
  const apply = useApplyResource()
  return useMutation({
    mutationFn: (body: ResourceStatusChange) => changeResourceStatus(id, body),
    onSuccess: apply,
  })
}
