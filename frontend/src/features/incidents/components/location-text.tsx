import { MapPinOff } from "lucide-react"
import { useTranslation } from "react-i18next"

import { formatCoordinates } from "@/lib/format"

import type { IncidentLocation } from "../types"

/** Coordenadas de una ubicación, o «Sin coordenadas» (icono + texto). */
export function CoordinatesText({ location }: { location: IncidentLocation }) {
  const { t } = useTranslation()
  if (location.latitude === null || location.longitude === null) {
    return (
      <span className="inline-flex items-center gap-1.5 text-muted-foreground">
        <MapPinOff aria-hidden className="size-3.5 shrink-0" />
        {t("incidents.location.noCoordinates")}
      </span>
    )
  }
  return (
    <span className="font-data">{formatCoordinates(location.latitude, location.longitude)}</span>
  )
}
