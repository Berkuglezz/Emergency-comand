import { CircleCheck } from "lucide-react"
import { useTranslation } from "react-i18next"

import { cn } from "@/lib/utils"
import type { components } from "@/types/api"

import { type IncidentPriority, PRIORITY_ICONS, PRIORITY_TONE } from "./priority"
import { MARKER_BORDER_CLASS, MARKER_STATUS_STYLE } from "./marker-style"
import { TONE_STYLES } from "./tones"

type IncidentStatus = components["schemas"]["IncidentStatus"]

interface IncidentMarkerProps {
  code: string
  title: string
  priority: IncidentPriority
  status: IncidentStatus
  isSimulated: boolean
  selected?: boolean
  onClick?: () => void
  className?: string
}

/**
 * Incidente en el mapa: botón compacto con icono y color de prioridad y borde
 * según el estado, para que no se solapen a escala regional. El código se
 * muestra al seleccionarlo y en el tooltip (ratón o foco). El nombre
 * accesible lo dice todo: el color nunca va solo.
 */
export function IncidentMarker({
  code,
  title,
  priority,
  status,
  isSimulated,
  selected = false,
  onClick,
  className,
}: IncidentMarkerProps) {
  const { t } = useTranslation()
  const tone = TONE_STYLES[PRIORITY_TONE[priority]]
  const Icon = PRIORITY_ICONS[priority]
  const finished = status === "closed" || status === "cancelled"
  const description = [
    code,
    t("ops.marker.priority", { priority: t(`priority.${priority}`) }),
    t(`incidentStatus.${status}`),
    isSimulated ? t("ops.simulated") : null,
  ]
    .filter(Boolean)
    .join(", ")

  return (
    <button
      type="button"
      aria-label={description}
      aria-pressed={selected}
      data-priority={priority}
      data-status={status}
      onClick={onClick}
      className={cn(
        "group relative flex h-6 min-w-6 items-center justify-center gap-1 rounded-sm border-2 border-current bg-surface-1 px-0.5 font-data text-xs font-medium outline-none",
        "focus-visible:ring-3 focus-visible:ring-ring/50",
        tone.text,
        MARKER_BORDER_CLASS[MARKER_STATUS_STYLE[status]],
        selected && "px-1 ring-2 ring-text",
        finished && "opacity-70",
        priority === "critical" && !finished && "critical-pulse",
        className
      )}
    >
      <Icon aria-hidden className="size-3.5 shrink-0" />
      {selected && <span className="text-text">{code}</span>}
      {status === "controlled" && <CircleCheck aria-hidden className="size-3.5 text-ok" />}
      {/* Tooltip visual; el nombre accesible ya incluye la misma información. */}
      <span
        aria-hidden
        className="pointer-events-none absolute bottom-full left-1/2 mb-1 hidden w-max max-w-64 -translate-x-1/2 flex-col rounded-sm border bg-popover px-2 py-1 text-left font-sans text-xs font-normal text-popover-foreground group-hover:flex group-focus-visible:flex"
      >
        <span className="font-medium">{title}</span>
        <span className="text-muted-foreground">{description}</span>
      </span>
    </button>
  )
}
