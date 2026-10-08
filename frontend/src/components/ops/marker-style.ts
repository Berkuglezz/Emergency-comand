import type { components } from "@/types/api"

type IncidentStatus = components["schemas"]["IncidentStatus"]

/**
 * Borde del marcador según el estado (la prioridad ya usa el color):
 * discontinuo = sin intervenir; continuo = en intervención; punteado =
 * finalizado. «Controlado» añade un icono de check.
 */
export const MARKER_STATUS_STYLE: Record<IncidentStatus, "dashed" | "solid" | "dotted"> = {
  received: "dashed",
  assessing: "dashed",
  resources_assigned: "solid",
  in_progress: "solid",
  controlled: "solid",
  closed: "dotted",
  cancelled: "dotted",
}

export const MARKER_BORDER_CLASS = {
  dashed: "border-dashed",
  solid: "border-solid",
  dotted: "border-dotted",
} as const
