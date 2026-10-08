import { LocateFixed, Scan } from "lucide-react"
import { type ReactNode, useEffect } from "react"
import { useTranslation } from "react-i18next"

import { IncidentMarker } from "@/components/ops/incident-marker"
import { Button } from "@/components/ui/button"
import type { IncidentMapFeature } from "@/features/incidents/types"

import { ASTURIAS_BOUNDS, type LngLat, POINT_ZOOM, prefersReducedMotion } from "./config"
import { MapFrame, MapMarker } from "./map-parts"
import { type MapLibreMap, useMapLibre } from "./use-maplibre"

export interface IncidentsMapProps {
  features: IncidentMapFeature[]
  selectedId: string | null
  onSelect: (id: string) => void
  /** Capas propias sobre el mapa (aviso de datos simulados, leyenda…). */
  overlay?: ReactNode
  className?: string
}

/** Mapa del centro de mando: un marcador por incidente con coordenadas. */
export default function IncidentsMap({
  features,
  selectedId,
  onSelect,
  overlay,
  className,
}: IncidentsMapProps) {
  const { t } = useTranslation()
  const { map, status, containerRef } = useMapLibre({ bounds: ASTURIAS_BOUNDS })
  const selected = features.find((feature) => feature.properties.id === selectedId)
  const [selectedLongitude, selectedLatitude] = selected?.geometry.coordinates ?? []

  // Seleccionar desde la lista centra el incidente si no está a la vista (sin
  // cambiar el zoom). Con movimiento reducido, sin animación.
  useEffect(() => {
    if (!map || selectedLongitude === undefined || selectedLatitude === undefined) return
    const position: LngLat = [selectedLongitude, selectedLatitude]
    if (!map.getBounds().contains(position)) {
      map.easeTo({ center: position, animate: !prefersReducedMotion() })
    }
  }, [map, selectedLongitude, selectedLatitude])

  return (
    <MapFrame
      status={status}
      containerRef={containerRef}
      label={t("map.incidentsLabel")}
      className={className}
      overlay={
        <>
          {overlay}
          {map && (
            <div className="absolute bottom-7 left-2 z-10 flex flex-col gap-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  fitToIncidents(map, features)
                }}
                disabled={features.length === 0}
              >
                <Scan data-icon="inline-start" aria-hidden />
                {t("map.fitIncidents")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  map.fitBounds(ASTURIAS_BOUNDS, { padding: 16, animate: !prefersReducedMotion() })
                }}
              >
                <LocateFixed data-icon="inline-start" aria-hidden />
                {t("map.centerAsturias")}
              </Button>
            </div>
          )}
        </>
      }
    >
      {map &&
        features.map((feature) => {
          const { properties } = feature
          const [longitude, latitude] = feature.geometry.coordinates
          const isSelected = properties.id === selectedId
          return (
            <MapMarker
              key={properties.id}
              map={map}
              longitude={longitude}
              latitude={latitude}
              raised={isSelected}
            >
              <IncidentMarker
                code={properties.code}
                title={properties.title}
                priority={properties.priority}
                status={properties.status}
                isSimulated={properties.is_simulated}
                selected={isSelected}
                onClick={() => {
                  onSelect(properties.id)
                }}
              />
            </MapMarker>
          )
        })}
    </MapFrame>
  )
}

/** Encuadra todos los marcadores; con uno solo, lo centra con un zoom fijo. */
function fitToIncidents(map: MapLibreMap, features: IncidentMapFeature[]): void {
  const animate = !prefersReducedMotion()
  const points = features.map((feature) => feature.geometry.coordinates)
  const [first] = points
  if (!first) return
  if (points.length === 1) {
    map.easeTo({ center: first, zoom: POINT_ZOOM, animate })
    return
  }
  const longitudes = points.map(([longitude]) => longitude)
  const latitudes = points.map(([, latitude]) => latitude)
  map.fitBounds(
    [
      [Math.min(...longitudes), Math.min(...latitudes)],
      [Math.max(...longitudes), Math.max(...latitudes)],
    ],
    { padding: 48, maxZoom: POINT_ZOOM, animate }
  )
}
