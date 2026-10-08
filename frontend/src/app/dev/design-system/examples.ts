/*
 * Valores de ejemplo del catálogo /dev/design-system (CLAUDE.md §2.1).
 * Estáticos, solo para esta ruta de desarrollo. No se importan desde ningún
 * otro sitio.
 */

import type { IncidentPriority } from "@/components/ops/priority"
import type { Tone } from "@/components/ops/tones"

export const SURFACE_TOKENS = [
  "--bg",
  "--surface-1",
  "--surface-2",
  "--border",
  "--text",
  "--text-muted",
] as const

export const TYPE_SCALE = [
  { className: "text-xs", label: "text-xs · 11/16" },
  { className: "text-sm", label: "text-sm · 13/20 (base)" },
  { className: "text-base", label: "text-base · 14/20" },
  { className: "text-lg", label: "text-lg · 16/24" },
  { className: "text-xl", label: "text-xl · 18/24" },
  { className: "text-2xl", label: "text-2xl · 22/28" },
  { className: "text-3xl", label: "text-3xl · 28/32" },
] as const

export const DATA_SAMPLES = {
  code: "INC-0042",
  time: "14:07:31",
  coordinates: "43.3614, -5.8494",
} as const

export const RADII = [
  { className: "rounded-sm", value: "4px" },
  { className: "rounded-md", value: "5px" },
  { className: "rounded-lg", value: "6px" },
] as const

export const TABLE_ROWS: readonly {
  code: string
  priority: IncidentPriority
  tone: Tone
  time: string
}[] = [
  { code: "INC-0042", priority: "critical", tone: "critical", time: "14:07:31" },
  { code: "INC-0041", priority: "high", tone: "info", time: "13:52:10" },
  { code: "INC-0039", priority: "medium", tone: "warning", time: "13:20:44" },
  { code: "INC-0035", priority: "low", tone: "ok", time: "12:03:09" },
  { code: "INC-0031", priority: "low", tone: "inactive", time: "09:41:57" },
]

export const KPI_SAMPLES = {
  active: 12,
  critical: 3,
  availability: 87,
} as const
