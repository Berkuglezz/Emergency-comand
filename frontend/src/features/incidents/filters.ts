/**
 * Filtros del listado de incidentes guardados en la URL (`/incidents?…`), para
 * que se puedan compartir y sobrevivan a una recarga. Un valor desconocido en
 * la URL se ignora en lugar de enviarse a la API.
 */
import { PRIORITY_CODES } from "@/components/ops/priority"
import { oneOf, pageFrom } from "@/lib/query-string"

import { STATUS_CODES } from "./presentation"
import type { IncidentListParams, IncidentPriority, IncidentSort, IncidentStatus } from "./types"

export const PAGE_SIZE = 25

/** Orden → valor de la API. Las claves son las etiquetas de `incidents.sort`. */
export const SORT_OPTIONS = {
  priority: "priority",
  reportedDesc: "-reported_at",
  reportedAsc: "reported_at",
  updatedDesc: "-updated_at",
} as const satisfies Record<string, IncidentSort>

const SORT_VALUES: readonly string[] = Object.values(SORT_OPTIONS)

export interface IncidentFilters {
  q: string
  status: IncidentStatus | null
  priority: IncidentPriority | null
  type: string | null
  includeClosed: boolean
  sort: IncidentSort
  page: number
}

export function parseFilters(search: URLSearchParams): IncidentFilters {
  const sort = search.get("sort")
  const type = search.get("type")?.trim()
  return {
    q: search.get("q")?.trim() ?? "",
    status: oneOf(STATUS_CODES, search.get("status")),
    priority: oneOf(PRIORITY_CODES, search.get("priority")),
    type: type !== undefined && type !== "" ? type : null,
    includeClosed: search.get("closed") === "1",
    sort: sort !== null && SORT_VALUES.includes(sort) ? (sort as IncidentSort) : "priority",
    page: pageFrom(search.get("page")),
  }
}

/** Solo se escriben en la URL los valores distintos del valor por defecto. */
export function serializeFilters(filters: IncidentFilters): URLSearchParams {
  const search = new URLSearchParams()
  if (filters.q) search.set("q", filters.q)
  if (filters.status) search.set("status", filters.status)
  if (filters.priority) search.set("priority", filters.priority)
  if (filters.type) search.set("type", filters.type)
  if (filters.includeClosed) search.set("closed", "1")
  if (filters.sort !== "priority") search.set("sort", filters.sort)
  if (filters.page > 1) search.set("page", String(filters.page))
  return search
}

export function hasActiveFilters(filters: IncidentFilters): boolean {
  return (
    filters.q !== "" ||
    filters.status !== null ||
    filters.priority !== null ||
    filters.type !== null ||
    filters.includeClosed
  )
}

export function toListParams(filters: IncidentFilters): IncidentListParams {
  return {
    q: filters.q || undefined,
    status: filters.status ? [filters.status] : undefined,
    priority: filters.priority ? [filters.priority] : undefined,
    type: filters.type ?? undefined,
    // Un estado elegido explícitamente (p. ej. «Cerrado») se busca entre todos.
    active: !(filters.includeClosed || filters.status !== null),
    sort: filters.sort,
    limit: PAGE_SIZE,
    offset: (filters.page - 1) * PAGE_SIZE,
  }
}
