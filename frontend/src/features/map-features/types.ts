import type { components } from "@/types/api"

// Tipos generados desde el OpenAPI del backend (no se duplican a mano).
type Schemas = components["schemas"]

/**
 * Elemento dibujado sobre el mapa de un incidente (CLAUDE.md §2.12). No
 * confundir con `IncidentMapFeature`, que es el marcador de un incidente.
 */
export type MapFeature = Schemas["MapFeatureResponse"]
export type MapFeatureCollection = Schemas["MapFeatureCollection"]
export type MapFeatureKind = Schemas["MapFeatureKind"]
