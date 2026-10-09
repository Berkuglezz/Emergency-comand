import { Clock, CircleHelp } from "lucide-react"
import { useTranslation } from "react-i18next"

import { formatNumber, formatTime } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { components } from "@/types/api"

type Eta = components["schemas"]["EtaResponse"]
type EtaUnavailable = components["schemas"]["EtaUnavailable"]

interface EtaTextProps {
  eta: Eta | null
  /** Motivo si no hay estimación. */
  unavailable?: EtaUnavailable | null
  /** Hora de la asignación: añade la llegada estimada (hora a hora, no exacta). */
  assignedAt?: string
  className?: string
}

/**
 * ETA **estimada** (distancia * sinuosidad / velocidad media del tipo).
 * Siempre con icono y con la palabra «estimado»: nunca se presenta como exacta.
 */
export function EtaText({ eta, unavailable, assignedAt, className }: EtaTextProps) {
  const { t } = useTranslation()
  if (!eta) {
    return (
      <span className={cn("inline-flex items-center gap-1.5 text-muted-foreground", className)}>
        <CircleHelp aria-hidden className="size-3.5 shrink-0" />
        {unavailable ? t(`ops.eta.unavailable.${unavailable}`) : t("ops.eta.none")}
      </span>
    )
  }
  const arrival = assignedAt ? new Date(Date.parse(assignedAt) + eta.minutes * 60_000) : null
  return (
    <span className={cn("inline-flex flex-wrap items-center gap-x-1.5", className)}>
      <Clock aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
      <span className="font-data">
        {t("ops.eta.value", {
          minutes: formatNumber(eta.minutes),
          distance: formatNumber(eta.distance_km),
        })}
      </span>
      <span className="text-muted-foreground">{t("ops.eta.estimated")}</span>
      {arrival && (
        <span className="text-muted-foreground">
          {t("ops.eta.arrival", { time: formatTime(arrival).slice(0, 5) })}
        </span>
      )}
    </span>
  )
}
