import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

import { TONE_ICONS, TONE_STYLES, type Tone } from "./tones"

interface StatusPillProps {
  tone: Tone
  /** Texto del estado (ya traducido). Obligatorio: el color nunca va solo. */
  children: ReactNode
  /** Sustituye al icono por defecto del tono. */
  icon?: LucideIcon
  /** Pulso de atención. Solo tiene efecto en el tono crítico. */
  pulse?: boolean
  className?: string
}

/** Estado de una entidad o del sistema (conexión, disponibilidad…). */
export function StatusPill({ tone, children, icon, pulse = false, className }: StatusPillProps) {
  const styles = TONE_STYLES[tone]
  const Icon = icon ?? TONE_ICONS[tone]

  return (
    <Badge
      variant="outline"
      data-tone={tone}
      className={cn(
        // §7: radios de 4–6 px; la píldora se distingue del PriorityBadge (4 px) por el radio de 6 px.
        "rounded-lg",
        styles.text,
        styles.subtle,
        styles.border,
        pulse && tone === "critical" && "critical-pulse",
        className
      )}
    >
      <Icon data-icon="inline-start" aria-hidden />
      {children}
    </Badge>
  )
}
