import type { TFunction } from "i18next"
import {
  Activity,
  Ban,
  CircleCheckBig,
  FilePlus2,
  FolderTree,
  Inbox,
  ListChecks,
  type LucideIcon,
  MapPinned,
  NotebookPen,
  PencilLine,
  ScanSearch,
  ShieldCheck,
  Signal,
  Truck,
} from "lucide-react"

import type { Tone } from "@/components/ops/tones"
import { ApiError } from "@/lib/api-client"

import type { IncidentEventType, IncidentStatus } from "./types"

/**
 * Estado → tono e icono. El color comunica el estado (CLAUDE.md §7) y cada
 * estado tiene un icono propio, para que se distinga también sin color.
 */
export const STATUS_TONE: Record<IncidentStatus, Tone> = {
  received: "warning",
  assessing: "warning",
  resources_assigned: "info",
  in_progress: "info",
  controlled: "ok",
  closed: "inactive",
  cancelled: "inactive",
}

export const STATUS_ICONS: Record<IncidentStatus, LucideIcon> = {
  received: Inbox,
  assessing: ScanSearch,
  resources_assigned: Truck,
  in_progress: Activity,
  controlled: ShieldCheck,
  closed: CircleCheckBig,
  cancelled: Ban,
}

/** Todos los estados, en el orden del flujo (para filtros). */
export const STATUS_CODES = Object.keys(STATUS_TONE) as IncidentStatus[]

/** Cerrar y cancelar son irreversibles: exigen confirmación explícita (CLAUDE.md §6). */
export function isIrreversible(status: IncidentStatus): boolean {
  return status === "closed" || status === "cancelled"
}

export const EVENT_ICONS: Record<IncidentEventType, LucideIcon> = {
  incident_created: FilePlus2,
  status_changed: ListChecks,
  priority_changed: Signal,
  incident_updated: PencilLine,
  note_added: NotebookPen,
  parent_changed: FolderTree,
  location_changed: MapPinned,
}

const KNOWN_ERRORS = [
  "version_conflict",
  "invalid_transition",
  "incident_closed",
  "invalid_parent",
  "invalid_details",
  "details_not_allowed",
  "field_not_nullable",
  "incident_type_not_found",
  "incident_not_found",
  "permission_denied",
  "validation_error",
  "network_error",
] as const
type KnownError = (typeof KNOWN_ERRORS)[number]

function isKnownError(code: string): code is KnownError {
  return (KNOWN_ERRORS as readonly string[]).includes(code)
}

/** Mensaje para el usuario a partir del código estable que devuelve la API. */
export function incidentErrorMessage(error: unknown, t: TFunction): string {
  if (error instanceof ApiError && isKnownError(error.code)) {
    return t(`incidents.errors.${error.code}`)
  }
  return t("incidents.errors.unexpected")
}
