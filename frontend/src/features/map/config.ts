/**
 * Configuración del mapa (Fase 3). Sin dependencias de MapLibre: lo pueden
 * importar componentes que no cargan el mapa.
 *
 * Orden de coordenadas: MapLibre y GeoJSON usan `[longitud, latitud]`.
 */

/** Estilo del mapa base. OpenFreeMap no necesita clave; se puede sustituir
 * (p. ej. por un estilo local) con `VITE_MAP_STYLE_URL`. Al proveedor solo se
 * le piden teselas: nunca se le envían coordenadas ni datos de incidentes. */
const DEFAULT_STYLE_URL = "https://tiles.openfreemap.org/styles/dark"
const configuredStyleUrl = import.meta.env.VITE_MAP_STYLE_URL?.trim()
// Una variable vacía cuenta como no configurada.
export const MAP_STYLE_URL =
  configuredStyleUrl === undefined || configuredStyleUrl === ""
    ? DEFAULT_STYLE_URL
    : configuredStyleUrl

export type LngLat = [longitude: number, latitude: number]
export type Bounds = [southWest: LngLat, northEast: LngLat]

/** Encuadre inicial: Asturias. */
export const ASTURIAS_BOUNDS: Bounds = [
  [-7.2, 42.85],
  [-4.5, 43.7],
]

/**
 * Área de la demo (Asturias con margen). Es la misma regla que aplica el
 * backend (`app/domain/geo.py`, `location_out_of_area`); aquí solo sirve para
 * avisar antes de enviar el formulario. El backend sigue siendo quien decide.
 */
export const DEMO_AREA = {
  minLatitude: 42.8,
  maxLatitude: 43.8,
  minLongitude: -7.3,
  maxLongitude: -4.4,
}

export function inDemoArea(latitude: number, longitude: number): boolean {
  return (
    latitude >= DEMO_AREA.minLatitude &&
    latitude <= DEMO_AREA.maxLatitude &&
    longitude >= DEMO_AREA.minLongitude &&
    longitude <= DEMO_AREA.maxLongitude
  )
}

/** Zoom al centrar un único punto. */
export const POINT_ZOOM = 13

/** Respeta `prefers-reduced-motion`: sin animaciones de cámara si se ha pedido. */
export function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false
}
