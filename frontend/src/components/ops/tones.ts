import {
  CircleAlert,
  CircleCheck,
  CircleDashed,
  Info,
  type LucideIcon,
  OctagonAlert,
  TriangleAlert,
} from "lucide-react"

/** Semánticas de estado de CLAUDE.md §7. Solo comunican estado, nunca decoran. */
export const TONES = ["critical", "high", "warning", "ok", "info", "inactive"] as const
export type Tone = (typeof TONES)[number]

/** Variantes de cada color: texto, fondo tenue y borde (clases completas para Tailwind). */
export const TONE_STYLES: Record<Tone, { text: string; subtle: string; border: string }> = {
  critical: {
    text: "text-critical",
    subtle: "bg-critical-subtle",
    border: "border-critical-border",
  },
  high: { text: "text-high", subtle: "bg-high-subtle", border: "border-high-border" },
  warning: { text: "text-warning", subtle: "bg-warning-subtle", border: "border-warning-border" },
  ok: { text: "text-ok", subtle: "bg-ok-subtle", border: "border-ok-border" },
  info: { text: "text-info", subtle: "bg-info-subtle", border: "border-info-border" },
  inactive: {
    text: "text-inactive",
    subtle: "bg-inactive-subtle",
    border: "border-inactive-border",
  },
}

/**
 * Icono por defecto de cada tono. El color nunca va solo: siempre se acompaña
 * de icono y texto. Las formas son distintas entre sí (octógono, triángulo,
 * círculo…) para que se distingan también sin color.
 */
export const TONE_ICONS: Record<Tone, LucideIcon> = {
  critical: OctagonAlert,
  high: TriangleAlert,
  warning: CircleAlert,
  ok: CircleCheck,
  info: Info,
  inactive: CircleDashed,
}
