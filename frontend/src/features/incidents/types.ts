import type { components, operations } from "@/types/api"

// Tipos generados desde el OpenAPI del backend (no se duplican a mano).
type Schemas = components["schemas"]

export type { IncidentPriority } from "@/components/ops/priority"
export type IncidentStatus = Schemas["IncidentStatus"]
export type IncidentType = Schemas["IncidentTypeResponse"]
export type IncidentSummary = Schemas["IncidentSummary"]
export type IncidentDetail = Schemas["IncidentDetail"]
export type IncidentRef = Schemas["IncidentRef"]
export type IncidentPage = Schemas["IncidentPage"]
export type IncidentEvent = Schemas["IncidentEventResponse"]
export type IncidentEventType = Schemas["IncidentEventType"]
export type IncidentCreate = Schemas["IncidentCreate"]
export type IncidentUpdate = Schemas["IncidentUpdate"]
export type IncidentStatusChange = Schemas["IncidentStatusChange"]
export type IncidentNoteCreate = Schemas["IncidentNoteCreate"]
export type IncidentLocation = Schemas["LocationResponse"]
export type IncidentMapCollection = Schemas["IncidentMapCollection"]
export type IncidentMapFeature = Schemas["IncidentMapFeature"]

export type IncidentListParams = NonNullable<
  operations["list_incidents_api_v1_incidents_get"]["parameters"]["query"]
>
export type IncidentSort = NonNullable<IncidentListParams["sort"]>
export type IncidentMapParams = NonNullable<
  operations["map_incidents_api_v1_incidents_map_get"]["parameters"]["query"]
>
