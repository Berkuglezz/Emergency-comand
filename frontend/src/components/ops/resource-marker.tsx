import { Warehouse } from "lucide-react"
import { useTranslation } from "react-i18next"

import { cn } from "@/lib/utils"

export interface ResourceMarkerItem {
  code: string
  /** Tipo de recurso ya traducido. */
  typeLabel: string
  /** ETA estimada ya formateada (o motivo de que no haya). */
  etaLabel: string
}

interface ResourceMarkerProps {
  /** Recursos asignados con base en este punto (varios pueden compartir base). */
  items: ResourceMarkerItem[]
  className?: string
}

/**
 * Base de los recursos asignados al incidente seleccionado. Forma distinta a
 * la del incidente (cuadrada, borde neutro, icono de base) para no
 * confundirlos. Si varios comparten base, un solo marcador los nombra a todos
 * («+N»). No es interactivo: el detalle está en el panel lateral.
 */
export function ResourceMarker({ items, className }: ResourceMarkerProps) {
  const { t } = useTranslation()
  const [first] = items
  if (!first) return null
  const description = t("ops.resourceMarker.label", {
    resources: items
      .map((item) =>
        t("ops.resourceMarker.item", { ...item, type: item.typeLabel, eta: item.etaLabel })
      )
      .join("; "),
  })
  return (
    <span
      role="img"
      aria-label={description}
      title={description}
      data-resources={items.map((item) => item.code).join(" ")}
      className={cn(
        "flex h-6 items-center gap-1 rounded-xs border-2 border-text-muted bg-surface-2 px-1 font-data text-xs text-text",
        className
      )}
    >
      <Warehouse aria-hidden className="size-3.5 shrink-0" />
      {first.code}
      {items.length > 1 && <span aria-hidden>+{items.length - 1}</span>}
    </span>
  )
}
