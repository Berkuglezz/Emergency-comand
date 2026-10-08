import { MapPinOff } from "lucide-react"
import { Suspense } from "react"
import { useTranslation } from "react-i18next"

import { Skeleton } from "@/components/ui/skeleton"
import { PointMap } from "@/features/map/lazy"

import type { IncidentDetail } from "../types"

/** Minimapa de solo lectura de la ficha, o el estado «sin coordenadas». */
export function LocationMinimap({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation()
  const { latitude, longitude } = incident.location

  if (latitude === null || longitude === null) {
    return (
      <div className="flex h-48 flex-col items-center justify-center gap-1 rounded-md border border-dashed text-muted-foreground">
        <MapPinOff aria-hidden className="size-5" />
        <p>{t("incidents.location.noCoordinates")}</p>
        <p className="text-xs">{t("incidents.location.noCoordinatesHint")}</p>
      </div>
    )
  }
  return (
    <Suspense fallback={<Skeleton className="h-48" />}>
      <PointMap
        point={[longitude, latitude]}
        label={t("incidents.location.mapLabel", { code: incident.code })}
        className="h-48"
      />
    </Suspense>
  )
}
