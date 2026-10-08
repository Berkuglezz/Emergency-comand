import { MapPin } from "lucide-react"
import { useEffect } from "react"

import { ASTURIAS_BOUNDS, type LngLat, POINT_ZOOM } from "./config"
import { MapFrame, MapMarker } from "./map-parts"
import { useMapLibre } from "./use-maplibre"

export interface PointMapProps {
  /** Punto `[longitud, latitud]`; `null` = sin coordenadas. */
  point: LngLat | null
  /** Nombre accesible del mapa. */
  label: string
  /** Si se indica, un clic en el mapa (o arrastrar el punto) elige la posición. */
  onPick?: (position: LngLat) => void
  className?: string
}

/** Mapa de un único punto: minimapa de la ficha y selector del formulario. */
export default function PointMap({ point, label, onPick, className }: PointMapProps) {
  const { map, status, containerRef } = useMapLibre(
    point ? { center: point, zoom: POINT_ZOOM } : { bounds: ASTURIAS_BOUNDS }
  )

  useEffect(() => {
    if (!map || !onPick) return
    const pick = (event: { lngLat: { lng: number; lat: number } }) => {
      onPick([event.lngLat.lng, event.lngLat.lat])
    }
    map.on("click", pick)
    map.getCanvas().style.cursor = "crosshair"
    return () => {
      map.off("click", pick)
    }
  }, [map, onPick])

  return (
    <MapFrame status={status} containerRef={containerRef} label={label} className={className}>
      {map && point && (
        <MapMarker
          map={map}
          longitude={point[0]}
          latitude={point[1]}
          draggable={Boolean(onPick)}
          onDragEnd={onPick}
        >
          <MapPin aria-hidden className="size-7 -translate-y-3 fill-surface-1 text-text" />
        </MapMarker>
      )}
    </MapFrame>
  )
}
