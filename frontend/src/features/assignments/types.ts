import type { components, operations } from "@/types/api"

// Tipos generados desde el OpenAPI del backend (no se duplican a mano).
type Schemas = components["schemas"]

export type Assignment = Schemas["AssignmentResponse"]
export type AssignmentCandidate = Schemas["AssignmentCandidate"]
export type AssignmentCreate = Schemas["AssignmentCreate"]
export type AssignmentRelease = Schemas["AssignmentRelease"]
export type ReleaseReason = Schemas["ReleaseReason"]
export type CandidateParams = NonNullable<
  operations["list_assignment_candidates_api_v1_incidents__incident_id__assignment_candidates_get"]["parameters"]["query"]
>
