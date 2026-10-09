import type { TFunction } from "i18next"
import { Activity, CircleCheck, type LucideIcon, Wrench } from "lucide-react"

import type { Tone } from "@/components/ops/tones"
import { ApiError } from "@/lib/api-client"

import type { ResourceStatus } from "./types"

/**
 * Estado operativo → tono e icono (CLAUDE.md §7: ok = disponible, info = en
 * servicio). «Fuera de servicio» es una advertencia: el recurso existe pero no
 * se puede usar. «Inactivo» queda para los recursos desactivados.
 */
export const RESOURCE_STATUS_TONE: Record<ResourceStatus, Tone> = {
  available: "ok",
  in_service: "info",
  out_of_service: "warning",
}

export const RESOURCE_STATUS_ICONS: Record<ResourceStatus, LucideIcon> = {
  available: CircleCheck,
  in_service: Activity,
  out_of_service: Wrench,
}

/** Estados en el orden de disponibilidad (para filtros y resúmenes). */
export const RESOURCE_STATUS_CODES = Object.keys(RESOURCE_STATUS_TONE) as ResourceStatus[]

const KNOWN_ERRORS = [
  "version_conflict",
  "concurrent_update",
  "invalid_transition",
  "resource_inactive",
  "resource_code_taken",
  "resource_type_not_found",
  "organization_not_found",
  "resource_not_found",
  "field_not_nullable",
  "resource_assigned",
  "coordinates_incomplete",
  "location_out_of_area",
  "permission_denied",
  "validation_error",
  "network_error",
] as const
type KnownError = (typeof KNOWN_ERRORS)[number]

function isKnownError(code: string): code is KnownError {
  return (KNOWN_ERRORS as readonly string[]).includes(code)
}

/** Mensaje para el usuario a partir del código estable que devuelve la API. */
export function resourceErrorMessage(error: unknown, t: TFunction): string {
  if (error instanceof ApiError && isKnownError(error.code)) {
    return t(`resources.errors.${error.code}`)
  }
  return t("resources.errors.unexpected")
}
