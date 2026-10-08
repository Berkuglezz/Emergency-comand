import type { components, operations } from "@/types/api"

// Tipos generados desde el OpenAPI del backend (no se duplican a mano).
type Schemas = components["schemas"]

export type Resource = Schemas["ResourceResponse"]
export type ResourceStatus = Schemas["ResourceStatus"]
export type ResourceType = Schemas["ResourceTypeResponse"]
export type ResourcePage = Schemas["ResourcePage"]
export type ResourceCreate = Schemas["ResourceCreate"]
export type ResourceUpdate = Schemas["ResourceUpdate"]
export type ResourceStatusChange = Schemas["ResourceStatusChange"]

export type ResourceListParams = NonNullable<
  operations["list_resources_api_v1_resources_get"]["parameters"]["query"]
>
export type ResourceSort = NonNullable<ResourceListParams["sort"]>
