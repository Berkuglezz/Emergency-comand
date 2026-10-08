/** Piezas de React sobre MapLibre: marcadores DOM y marco del mapa. */
import { Marker } from "maplibre-gl"
import { MonitorX, TriangleAlert } from "lucide-react"
import { type ReactNode, useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { useTranslation } from "react-i18next"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { cn } from "@/lib/utils"

import type { LngLat } from "./config"
import type { MapLibreMap, MapStatus } from "./use-maplibre"

interface MapMarkerProps {
  map: MapLibreMap
  longitude: number
  latitude: number
  /** Por encima del resto (p. ej. el seleccionado). */
  raised?: boolean
  draggable?: boolean
  onDragEnd?: (position: LngLat) => void
  children: ReactNode
}

/** Marcador DOM de MapLibre con contenido de React (botones accesibles). */
export function MapMarker({
  map,
  longitude,
  latitude,
  raised = false,
  draggable = false,
  onDragEnd,
  children,
}: MapMarkerProps) {
  const [element] = useState(() => document.createElement("div"))
  const markerRef = useRef<Marker | null>(null)
  const dragEndRef = useRef(onDragEnd)

  useEffect(() => {
    dragEndRef.current = onDragEnd
  }, [onDragEnd])

  useEffect(() => {
    const marker = new Marker({ element, anchor: "center", draggable })
      .setLngLat([longitude, latitude])
      .addTo(map)
    marker.on("dragend", () => {
      const position = marker.getLngLat()
      dragEndRef.current?.([position.lng, position.lat])
    })
    markerRef.current = marker
    return () => {
      marker.remove()
      markerRef.current = null
    }
    // La posición se actualiza en el efecto siguiente, sin recrear el marcador.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, element, draggable])

  useEffect(() => {
    markerRef.current?.setLngLat([longitude, latitude])
  }, [longitude, latitude])

  useEffect(() => {
    // El seleccionado se dibuja por encima del resto.
    if (raised) markerRef.current?.addClassName("z-10")
    else markerRef.current?.removeClassName("z-10")
  }, [raised, draggable, map])

  return createPortal(children, element)
}

interface MapFrameProps {
  status: MapStatus
  containerRef: (element: HTMLDivElement | null) => void
  /** Nombre accesible del mapa. */
  label: string
  /** Capas propias sobre el mapa (avisos, leyenda…). */
  overlay?: ReactNode
  /** Marcadores (`MapMarker`): se dibujan dentro del mapa mediante portales. */
  children?: ReactNode
  className?: string
}

/** Contenedor del mapa con la atribución obligatoria y los avisos de fallo. */
export function MapFrame({
  status,
  containerRef,
  label,
  overlay,
  children,
  className,
}: MapFrameProps) {
  const { t } = useTranslation()

  return (
    <div
      className={cn("relative min-h-0 overflow-hidden rounded-md border bg-surface-1", className)}
    >
      {status === "unsupported" ? (
        <div className="flex h-full items-center justify-center p-3">
          <Alert>
            <MonitorX aria-hidden />
            <AlertTitle>{t("map.unsupportedTitle")}</AlertTitle>
            <AlertDescription>{t("map.unsupportedDescription")}</AlertDescription>
          </Alert>
        </div>
      ) : (
        <div
          ref={containerRef}
          role="region"
          aria-label={label}
          // En línea: la hoja de MapLibre fija `.maplibregl-map { position: relative }`
          // y ganaría a la clase `absolute`, dejando el mapa con altura 0.
          style={{ position: "absolute", inset: 0 }}
        />
      )}

      {status === "basemap_error" && (
        <Alert className="absolute top-2 left-2 z-10 w-auto max-w-[calc(100%-4rem)]">
          <TriangleAlert aria-hidden />
          <AlertTitle>{t("map.basemapErrorTitle")}</AlertTitle>
          <AlertDescription>{t("map.basemapErrorDescription")}</AlertDescription>
        </Alert>
      )}

      {overlay}
      {children}

      {/* Atribución obligatoria de OpenFreeMap, OpenMapTiles y OpenStreetMap. */}
      <p className="absolute right-0 bottom-0 z-10 rounded-tl-sm bg-surface-1/90 px-1.5 py-0.5 text-xs text-muted-foreground">
        <a
          href="https://openfreemap.org"
          target="_blank"
          rel="noreferrer"
          className="underline-offset-2 hover:underline"
        >
          {t("map.attribution.openFreeMap")}
        </a>{" "}
        <a
          href="https://www.openmaptiles.org/"
          target="_blank"
          rel="noreferrer"
          className="underline-offset-2 hover:underline"
        >
          {t("map.attribution.openMapTiles")}
        </a>{" "}
        <a
          href="https://www.openstreetmap.org/copyright"
          target="_blank"
          rel="noreferrer"
          className="underline-offset-2 hover:underline"
        >
          {t("map.attribution.openStreetMap")}
        </a>
      </p>
    </div>
  )
}
