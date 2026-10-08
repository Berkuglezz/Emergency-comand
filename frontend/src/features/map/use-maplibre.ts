/**
 * Integración con MapLibre GL JS: creación del mapa y su ciclo de vida. Junto
 * con `map-parts.tsx`, es lo único que importa `maplibre-gl`, y solo se carga
 * dentro de los componentes diferidos (`lazy.ts`): ni el login ni el resto de
 * pantallas descargan la librería.
 */
import "maplibre-gl/dist/maplibre-gl.css"

import { Map as MapLibreMap, NavigationControl, setWorkerUrl } from "maplibre-gl"
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url"
import { useCallback, useState } from "react"
import { useTranslation } from "react-i18next"

import { type Bounds, type LngLat, MAP_STYLE_URL } from "./config"

// MapLibre 6 carga su worker como fichero propio: Vite lo publica con `?url`.
setWorkerUrl(workerUrl)

export type { MapLibreMap }

/**
 * - `loading`: creando el mapa o cargando el estilo.
 * - `ready`: mapa base cargado.
 * - `basemap_error`: el estilo o las teselas no responden. El mapa sigue
 *   funcionando (posiciones y marcadores) sobre un fondo liso.
 * - `unsupported`: el navegador no puede crear el mapa (sin WebGL2).
 */
export type MapStatus = "loading" | "ready" | "basemap_error" | "unsupported"

interface MapSetup {
  bounds?: Bounds
  center?: LngLat
  zoom?: number
  interactive?: boolean
}

/** Crea el mapa al montar el contenedor y lo destruye al desmontarlo. Las
 * opciones solo se leen al crearlo. */
export function useMapLibre(setup: MapSetup) {
  const [map, setMap] = useState<MapLibreMap | null>(null)
  const [status, setStatus] = useState<MapStatus>("loading")
  const [initial] = useState(setup)
  const { t } = useTranslation()

  // Ref de callback con limpieza (React 19): el mapa vive lo mismo que su contenedor.
  const containerRef = useCallback(
    (element: HTMLDivElement | null) => {
      if (!element) return
      let instance: MapLibreMap
      try {
        instance = new MapLibreMap({
          container: element,
          style: MAP_STYLE_URL,
          bounds: initial.bounds,
          fitBoundsOptions: { padding: 16 },
          center: initial.center,
          zoom: initial.zoom,
          interactive: initial.interactive ?? true,
          // Textos de los controles y del lienzo de MapLibre, en español.
          locale: {
            "Map.Title": t("map.controls.canvas"),
            "Marker.Title": t("map.controls.marker"),
            "NavigationControl.ZoomIn": t("map.controls.zoomIn"),
            "NavigationControl.ZoomOut": t("map.controls.zoomOut"),
            "NavigationControl.ResetBearing": t("map.controls.resetBearing"),
          },
          // La atribución la muestra `MapFrame`, siempre visible aunque falle el estilo.
          attributionControl: false,
          // Mapa plano, sin rotación ni inclinación: es un mapa de situación.
          dragRotate: false,
          pitchWithRotate: false,
          touchPitch: false,
        })
      } catch {
        setStatus("unsupported")
        return
      }
      instance.touchZoomRotate.disableRotation()
      if (initial.interactive ?? true) {
        instance.addControl(new NavigationControl({ showCompass: false }), "top-right")
      }
      let loaded = false
      instance.on("load", () => {
        loaded = true
        setStatus("ready")
      })
      // Un error antes de cargar el estilo = sin mapa base. Los errores de
      // teselas sueltas después de cargar no cambian el estado. No se
      // registra nada: el evento no contiene datos de incidentes, pero
      // tampoco aporta nada al usuario.
      instance.on("error", () => {
        if (!loaded) setStatus("basemap_error")
      })
      setMap(instance)
      return () => {
        instance.remove()
        setMap(null)
      }
    },
    [initial, t]
  )

  return { map, status, containerRef }
}
