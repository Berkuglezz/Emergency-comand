/**
 * Perímetros guardados del incidente seleccionado (mapa operativo, CLAUDE.md
 * §2.12, M.2). Solo representa: sin clics, sin edición y sin dibujo.
 *
 * Son capas GeoJSON de MapLibre (no marcadores DOM), así que los marcadores de
 * incidentes y bases quedan siempre por encima. Necesitan el estilo cargado:
 * sin mapa base (`basemap_error`) no se pueden añadir.
 */
import type { GeoJSONSource } from "maplibre-gl"
import { useEffect } from "react"

import type { MapFeature } from "@/features/map-features/types"

import type { MapLibreMap } from "./use-maplibre"

/** GeoJSON que acepta la fuente (sin depender de `@types/geojson`). */
type SourceData = Parameters<GeoJSONSource["setData"]>[0]

const SOURCE = "ec-perimeters"
const FILL_LAYER = "ec-perimeters-fill"
const LINE_LAYER = "ec-perimeters-line"

/**
 * Color de `--status-warning` (tokens.css): lo dibujado está «no validado».
 * MapLibre no lee variables CSS; si el token no se puede leer, el mismo valor.
 */
function perimeterColor(): string {
  const token = getComputedStyle(document.documentElement)
    .getPropertyValue("--status-warning")
    .trim()
  return token || "#eab308"
}

export function PerimeterLayer({ map, features }: { map: MapLibreMap; features: MapFeature[] }) {
  // La fuente y las capas viven lo mismo que el mapa: se crean una vez (el
  // componente solo se monta con el estilo ya cargado).
  useEffect(() => {
    if (map.getSource(SOURCE)) return
    const color = perimeterColor()
    map.addSource(SOURCE, { type: "geojson", data: { type: "FeatureCollection", features: [] } })
    map.addLayer({
      id: FILL_LAYER,
      type: "fill",
      source: SOURCE,
      paint: { "fill-color": color, "fill-opacity": 0.1 },
    })
    // Contorno discontinuo: dibujado, no validado (como el borde de los
    // marcadores sin intervenir, discontinuo = pendiente de confirmar).
    map.addLayer({
      id: LINE_LAYER,
      type: "line",
      source: SOURCE,
      layout: { "line-join": "round" },
      paint: { "line-color": color, "line-width": 2, "line-dasharray": [2, 1.5] },
    })
  }, [map])

  useEffect(() => {
    // La API ya devuelve GeoJSON válido (validado por el backend y PostGIS).
    // El identificador va en `properties`: MapLibre solo admite `id` numéricos.
    // `setData` devuelve una promesa (actualización en el worker); no hay nada que esperar.
    void map.getSource<GeoJSONSource>(SOURCE)?.setData({
      type: "FeatureCollection",
      features: features.map((feature) => ({
        type: "Feature",
        geometry: feature.geometry,
        properties: { id: feature.id },
      })),
    } as SourceData)
  }, [map, features])

  return null
}
