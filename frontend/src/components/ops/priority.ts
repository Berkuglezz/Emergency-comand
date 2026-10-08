import {
  CircleAlert,
  CircleArrowDown,
  type LucideIcon,
  OctagonAlert,
  TriangleAlert,
} from "lucide-react"

import type { components } from "@/types/api"

import type { Tone } from "./tones"

/** Prioridad de un incidente: tipo generado desde el OpenAPI del backend (fuente única). */
export type IncidentPriority = components["schemas"]["IncidentPriority"]

export const PRIORITY_TONE: Record<IncidentPriority, Tone> = {
  critical: "critical",
  high: "high",
  medium: "warning",
  low: "info",
}

export const PRIORITY_ICONS: Record<IncidentPriority, LucideIcon> = {
  critical: OctagonAlert,
  high: TriangleAlert,
  medium: CircleAlert,
  low: CircleArrowDown,
}

/** Orden de urgencia (menor = más urgente). Al ser un `Record`, TypeScript
 * exige una entrada por cada prioridad que exponga el backend. */
const PRIORITY_RANK: Record<IncidentPriority, number> = { critical: 0, high: 1, medium: 2, low: 3 }

/** Prioridades de la más a la menos urgente (para selectores y leyendas). */
export const PRIORITY_CODES = (Object.keys(PRIORITY_RANK) as IncidentPriority[]).sort(
  (a, b) => PRIORITY_RANK[a] - PRIORITY_RANK[b]
)
