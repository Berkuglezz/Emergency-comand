/**
 * Filtros del centro de mando en la URL (`/?priority=…&status=…`). Los
 * comparten el mapa y la lista de incidentes activos.
 */
import { PRIORITY_CODES } from "@/components/ops/priority"
import { isIrreversible, STATUS_CODES } from "@/features/incidents/presentation"
import type { IncidentPriority, IncidentStatus } from "@/features/incidents/types"
import { oneOf } from "@/lib/query-string"

/** Solo estados activos: cerrados y cancelados no aparecen en el centro de mando. */
export const ACTIVE_STATUS_CODES = STATUS_CODES.filter((status) => !isIrreversible(status))

export interface CommandCenterFilters {
  priority: IncidentPriority | null
  status: IncidentStatus | null
}

export function parseCommandCenterFilters(search: URLSearchParams): CommandCenterFilters {
  return {
    priority: oneOf(PRIORITY_CODES, search.get("priority")),
    status: oneOf(ACTIVE_STATUS_CODES, search.get("status")),
  }
}

/** Parámetros comunes de la API (listado y mapa): solo activos, con los filtros. */
export function toActiveQuery(filters: CommandCenterFilters) {
  return {
    active: true,
    priority: filters.priority ? [filters.priority] : undefined,
    status: filters.status ? [filters.status] : undefined,
  }
}
