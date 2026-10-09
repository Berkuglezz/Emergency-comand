import type { TFunction } from "i18next"

import { ApiError } from "@/lib/api-client"

import type { ReleaseReason } from "./types"

/** Todos los motivos de retirada (al ser un `Record`, TypeScript exige uno por cada
 * valor que exponga el backend). */
const RELEASE_REASON_SET: Record<ReleaseReason, true> = {
  completed: true,
  not_needed: true,
  unavailable: true,
  reassigned: true,
  incident_closed: true,
}
export const RELEASE_REASON_CODES = Object.keys(RELEASE_REASON_SET) as ReleaseReason[]

/** Motivos que puede elegir una persona; `reassigned` e `incident_closed` los pone el sistema. */
export const USER_RELEASE_REASONS = [
  "completed",
  "not_needed",
  "unavailable",
] as const satisfies readonly ReleaseReason[]

const KNOWN_ERRORS = [
  "version_conflict",
  "concurrent_update",
  "resource_already_assigned",
  "resource_not_available",
  "resource_inactive",
  "resource_not_found",
  "incident_closed",
  "incident_not_found",
  "assignment_not_found",
  "assignment_already_released",
  "assignment_already_arrived",
  "invalid_release_reason",
  "permission_denied",
  "validation_error",
  "network_error",
] as const
type KnownError = (typeof KNOWN_ERRORS)[number]

function isKnownError(code: string): code is KnownError {
  return (KNOWN_ERRORS as readonly string[]).includes(code)
}

/** Mensaje para el usuario a partir del código estable que devuelve la API. */
export function assignmentErrorMessage(error: unknown, t: TFunction): string {
  if (error instanceof ApiError && isKnownError(error.code)) {
    return t(`assignments.errors.${error.code}`)
  }
  return t("assignments.errors.unexpected")
}
