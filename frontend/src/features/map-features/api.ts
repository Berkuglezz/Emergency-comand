import { apiRequest } from "@/lib/api-client"

import type { MapFeatureCollection } from "./types"

/** Elementos activos del mapa operativo de un incidente (GeoJSON). Solo lectura. */
export function fetchIncidentMapFeatures(
  incidentId: string,
  signal?: AbortSignal
): Promise<MapFeatureCollection> {
  return apiRequest<MapFeatureCollection>(
    `/incidents/${encodeURIComponent(incidentId)}/map-features`,
    { signal }
  )
}
