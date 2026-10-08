import type { components } from "@/types/api"

// Tipos generados desde el OpenAPI del backend (no se duplican a mano).
export type SessionUser = components["schemas"]["MeResponse"]
export type Permission = components["schemas"]["Permission"]
export type RoleCode = components["schemas"]["RoleCode"]
export type TokenResponse = components["schemas"]["TokenResponse"]
export type LoginRequest = components["schemas"]["LoginRequest"]
