import { apiRequest } from "@/lib/api-client"
import { toQueryString } from "@/lib/query-string"

import type {
  Resource,
  ResourceCreate,
  ResourceListParams,
  ResourcePage,
  ResourceStatusChange,
  ResourceType,
  ResourceUpdate,
} from "./types"

export function fetchResourceTypes(signal?: AbortSignal): Promise<ResourceType[]> {
  return apiRequest<ResourceType[]>("/resource-types", { signal })
}

export function fetchResources(
  params: ResourceListParams,
  signal?: AbortSignal
): Promise<ResourcePage> {
  return apiRequest<ResourcePage>(`/resources${toQueryString(params)}`, { signal })
}

export function fetchResource(id: string, signal?: AbortSignal): Promise<Resource> {
  return apiRequest<Resource>(`/resources/${encodeURIComponent(id)}`, { signal })
}

export function createResource(body: ResourceCreate): Promise<Resource> {
  return apiRequest<Resource>("/resources", { method: "POST", body })
}

export function updateResource(id: string, body: ResourceUpdate): Promise<Resource> {
  return apiRequest<Resource>(`/resources/${encodeURIComponent(id)}`, { method: "PATCH", body })
}

export function changeResourceStatus(id: string, body: ResourceStatusChange): Promise<Resource> {
  return apiRequest<Resource>(`/resources/${encodeURIComponent(id)}/status`, {
    method: "POST",
    body,
  })
}
