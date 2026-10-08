import { useTranslation } from "react-i18next"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

import { type IncidentPriority, PRIORITY_ICONS, PRIORITY_TONE } from "./priority"
import { TONE_STYLES } from "./tones"

interface PriorityBadgeProps {
  priority: IncidentPriority
  /** Pulso de atención. Solo tiene efecto en prioridad crítica. */
  pulse?: boolean
  className?: string
}

/** Prioridad de un incidente: color + icono + texto, nunca solo color. */
export function PriorityBadge({ priority, pulse = false, className }: PriorityBadgeProps) {
  const { t } = useTranslation()
  const tone = TONE_STYLES[PRIORITY_TONE[priority]]
  const Icon = PRIORITY_ICONS[priority]

  return (
    <Badge
      variant="outline"
      data-priority={priority}
      className={cn(
        "rounded-sm",
        tone.text,
        tone.subtle,
        tone.border,
        pulse && priority === "critical" && "critical-pulse",
        className
      )}
    >
      <Icon data-icon="inline-start" aria-hidden />
      <span className="sr-only">{t("priority.label")}: </span>
      {t(`priority.${priority}`)}
    </Badge>
  )
}
