/**
 * Filtros del listado de recursos guardados en la URL (`/resources?…`). Un
 * valor desconocido en la URL se ignora en lugar de enviarse a la API.
 */
import { oneOf, pageFrom } from "@/lib/query-string"

import { RESOURCE_STATUS_CODES } from "./presentation"
import type { ResourceListParams, ResourceSort, ResourceStatus } from "./types"

export const PAGE_SIZE = 25

/** Orden → valor de la API. Las claves son las etiquetas de `resources.sort`. */
export const SORT_OPTIONS = {
  code: "code",
  status: "status",
  statusChangedDesc: "-status_changed_at",
} as const satisfies Record<string, ResourceSort>

const SORT_VALUES: readonly ResourceSort[] = Object.values(SORT_OPTIONS)

export interface ResourceFilters {
  q: string
  status: ResourceStatus | null
  type: string | null
  organization: string | null
  includeInactive: boolean
  sort: ResourceSort
  page: number
}

function text(value: string | null): string | null {
  const trimmed = value?.trim()
  return trimmed !== undefined && trimmed !== "" ? trimmed : null
}

export function parseFilters(search: URLSearchParams): ResourceFilters {
  return {
    q: text(search.get("q")) ?? "",
    status: oneOf(RESOURCE_STATUS_CODES, search.get("status")),
    type: text(search.get("type")),
    organization: text(search.get("organization")),
    includeInactive: search.get("inactive") === "1",
    sort: oneOf(SORT_VALUES, search.get("sort")) ?? "code",
    page: pageFrom(search.get("page")),
  }
}

/** Solo se escriben en la URL los valores distintos del valor por defecto. */
export function serializeFilters(filters: ResourceFilters): URLSearchParams {
  const search = new URLSearchParams()
  if (filters.q) search.set("q", filters.q)
  if (filters.status) search.set("status", filters.status)
  if (filters.type) search.set("type", filters.type)
  if (filters.organization) search.set("organization", filters.organization)
  if (filters.includeInactive) search.set("inactive", "1")
  if (filters.sort !== "code") search.set("sort", filters.sort)
  if (filters.page > 1) search.set("page", String(filters.page))
  return search
}

export function hasActiveFilters(filters: ResourceFilters): boolean {
  return (
    filters.q !== "" ||
    filters.status !== null ||
    filters.type !== null ||
    filters.organization !== null ||
    filters.includeInactive
  )
}

export function toListParams(filters: ResourceFilters): ResourceListParams {
  return {
    q: filters.q || undefined,
    status: filters.status ? [filters.status] : undefined,
    type: filters.type ?? undefined,
    organization_id: filters.organization ?? undefined,
    active: !filters.includeInactive,
    sort: filters.sort,
    limit: PAGE_SIZE,
    offset: (filters.page - 1) * PAGE_SIZE,
  }
}
