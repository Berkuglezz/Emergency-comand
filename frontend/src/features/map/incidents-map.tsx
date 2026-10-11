import { LocateFixed, Scan, Shapes } from "lucide-react"
import { type ReactNode, useEffect } from "react"
import { useTranslation } from "react-i18next"

import { IncidentMarker } from "@/components/ops/incident-marker"
import { ResourceMarker, type ResourceMarkerItem } from "@/components/ops/resource-marker"
import { Button } from "@/components/ui/button"
import type { IncidentMapFeature } from "@/features/incidents/types"
import { perimeterPoints } from "@/features/map-features/geometry"
import type { MapFeature } from "@/features/map-features/types"

import { ASTURIAS_BOUNDS, type LngLat, POINT_ZOOM, prefersReducedMotion } from "./config"
import { MapFrame, MapMarker } from "./map-parts"
import { PerimeterLayer } from "./perimeter-layer"
import { type MapLibreMap, useMapLibre } from "./use-maplibre"

/** Base (un punto) con los recursos asignados al incidente seleccionado que la comparten. */
export interface MapBase {
  id: string
  items: ResourceMarkerItem[]
  position: LngLat
}

export interface IncidentsMapProps {
  features: IncidentMapFeature[]
  /** Bases de los recursos asignados al incidente seleccionado (solo esas). */
  bases?: MapBase[]
  /** Perímetros guardados del incidente seleccionado (solo esos, solo lectura). */
  perimeters?: MapFeature[]
  selectedId: string | null
  onSelect: (id: string) => void
  /** Capas propias sobre el mapa (aviso de datos simulados, leyenda…). */
  overlay?: ReactNode
  className?: string
}

// Valor por defecto estable: un `[]` nuevo en cada render repetiría `setData`.
const NO_PERIMETERS: MapFeature[] = []

/** Mapa del centro de mando: un marcador por incidente con coordenadas. */
export default function IncidentsMap({
  features,
  bases = [],
  perimeters = NO_PERIMETERS,
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
  // cambiar el zoom). Con movimiento reducido, sin animación. También al
  // redimensionar el mapa (plegar o desplegar un panel): la selección no debe
  // quedar fuera del área visible.
  useEffect(() => {
    if (!map || selectedLongitude === undefined || selectedLatitude === undefined) return
    const position: LngLat = [selectedLongitude, selectedLatitude]
    const reveal = () => {
      if (!map.getBounds().contains(position)) {
        map.easeTo({ center: position, animate: !prefersReducedMotion() })
      }
    }
    reveal()
    map.on("resize", reveal)
    return () => {
      map.off("resize", reveal)
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
          {/* Controles propios, discretos, abajo a la derecha (encima de la
              atribución); el zoom de MapLibre queda arriba a la derecha. */}
          {map && (
            <div className="absolute right-2 bottom-7 z-10 flex flex-col gap-1">
              <Button
                variant="outline"
                size="icon-sm"
                aria-label={t("map.fitIncidents")}
                title={t("map.fitIncidents")}
                className="bg-surface-1"
                onClick={() => {
                  fitToPoints(map, [
                    ...features.map((feature) => feature.geometry.coordinates),
                    ...bases.map((base) => base.position),
                    ...perimeterPoints(perimeters),
                  ])
                }}
                disabled={features.length === 0}
              >
                <Scan aria-hidden />
              </Button>
              <Button
                variant="outline"
                size="icon-sm"
                aria-label={t("map.centerAsturias")}
                title={t("map.centerAsturias")}
                className="bg-surface-1"
                onClick={() => {
                  map.fitBounds(ASTURIAS_BOUNDS, { padding: 16, animate: !prefersReducedMotion() })
                }}
              >
                <LocateFixed aria-hidden />
              </Button>
            </div>
          )}
          {/* Sin mapa base no hay estilo y MapLibre no admite capas: el perímetro
              no se puede dibujar, pero sigue en el panel lateral. */}
          {status === "basemap_error" && perimeters.length > 0 && (
            <p className="absolute bottom-10 left-2 z-10 flex max-w-[calc(100%-6rem)] items-center gap-1.5 rounded-md border border-warning-border bg-surface-1/95 px-2 py-0.5 text-xs">
              <Shapes aria-hidden className="size-3.5 shrink-0 text-warning" />
              {t("map.perimeterUnavailable")}
            </p>
          )}
        </>
      }
    >
      {map && status === "ready" && <PerimeterLayer map={map} features={perimeters} />}
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
      {/* Bases de los recursos asignados: sin líneas hacia el incidente (no hay rutas). */}
      {map &&
        bases.map((base) => (
          <MapMarker
            key={base.id}
            map={map}
            longitude={base.position[0]}
            latitude={base.position[1]}
          >
            <ResourceMarker items={base.items} />
          </MapMarker>
        ))}
    </MapFrame>
  )
}

/** Encuadra todos los puntos visibles; con uno solo, lo centra con un zoom fijo. */
function fitToPoints(map: MapLibreMap, points: LngLat[]): void {
  const animate = !prefersReducedMotion()
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
