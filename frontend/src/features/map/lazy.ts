/**
 * Mapas con carga diferida: MapLibre solo se descarga en las pantallas que
 * muestran un mapa. Se usan dentro de `<Suspense>`.
 */
import { lazy } from "react"

export const IncidentsMap = lazy(() => import("./incidents-map"))
export const PointMap = lazy(() => import("./point-map"))
