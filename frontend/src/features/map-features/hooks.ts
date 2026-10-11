import { useQuery } from "@tanstack/react-query"

import { queryKeys } from "@/lib/query-keys"

import { fetchIncidentMapFeatures } from "./api"
import type { MapFeature, MapFeatureCollection } from "./types"

/** Lo que se representa en M.2: perímetros activos. Fuera de la función para
 * que `select` sea estable y el resultado no cambie de identidad en cada render. */
function activePerimeters(collection: MapFeatureCollection): MapFeature[] {
  return collection.features.filter(
    (feature) => feature.properties.kind === "perimeter" && feature.properties.status === "active"
  )
}

/**
 * Perímetros del incidente seleccionado. Mapa y panel lateral comparten la
 * misma consulta (caché). Sin `placeholderData`: al cambiar de incidente nunca
 * se muestra, ni un instante, el perímetro del anterior.
 */
export function useIncidentPerimeters(incidentId: string | null) {
  return useQuery({
    queryKey: queryKeys.incidentMapFeatures(incidentId ?? ""),
    queryFn: ({ signal }) => fetchIncidentMapFeatures(incidentId ?? "", signal),
    enabled: incidentId !== null,
    select: activePerimeters,
  })
}
