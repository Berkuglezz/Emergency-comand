import type { LngLat } from "@/features/map/config"

import type { MapFeature } from "./types"

/** Vértices de los perímetros, para encuadrarlos junto con los marcadores. */
export function perimeterPoints(features: MapFeature[]): LngLat[] {
  return features.flatMap((feature) => {
    const { type, coordinates } = feature.geometry
    if (type !== "Polygon" || !Array.isArray(coordinates)) return []
    return (coordinates as unknown[]).flatMap((ring) =>
      Array.isArray(ring)
        ? ring.filter(
            (position): position is LngLat =>
              Array.isArray(position) &&
              typeof position[0] === "number" &&
              typeof position[1] === "number"
          )
        : []
    )
  })
}
