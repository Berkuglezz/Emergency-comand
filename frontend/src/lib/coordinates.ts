/**
 * Coordenadas WGS84 escritas por el usuario (incidentes y bases de recursos).
 * Mismas reglas que el backend (`app/domain/geo.py`): ambas o ninguna, en
 * rango y dentro del área de la demo. El backend sigue siendo quien decide.
 */
import type { TFunction } from "i18next"
import type { z } from "zod"

import { inDemoArea } from "@/features/map/config"

const COORDINATE = /^-?\d{1,3}([.,]\d+)?$/
/** 6 decimales ≈ 11 cm, como redondea el backend. */
const COORDINATE_DECIMALS = 6

/** Coordenada escrita por el usuario → número redondeado, o `null` si no es válida. */
export function parseCoordinate(value: string): number | null {
  const text = value.trim()
  if (!COORDINATE.test(text)) return null
  const number = Number(text.replace(",", "."))
  return Number.isFinite(number) ? roundCoordinate(number) : null
}

export function roundCoordinate(value: number): number {
  return Number(value.toFixed(COORDINATE_DECIMALS))
}

/** Valida el par `latitude`/`longitude` de un formulario (en `superRefine`). */
export function refineCoordinates(
  values: { latitude: string; longitude: string },
  context: z.RefinementCtx,
  t: TFunction
): void {
  const latitudeText = values.latitude.trim()
  const longitudeText = values.longitude.trim()
  if (!latitudeText && !longitudeText) return
  const latitude = parseCoordinate(latitudeText)
  const longitude = parseCoordinate(longitudeText)
  if (latitude === null || latitude < -90 || latitude > 90) {
    context.addIssue({
      code: "custom",
      path: ["latitude"],
      message: latitudeText
        ? t("coordinates.validation.latitudeInvalid")
        : t("coordinates.validation.incomplete"),
    })
  }
  if (longitude === null || longitude < -180 || longitude > 180) {
    context.addIssue({
      code: "custom",
      path: ["longitude"],
      message: longitudeText
        ? t("coordinates.validation.longitudeInvalid")
        : t("coordinates.validation.incomplete"),
    })
  }
  if (latitude !== null && longitude !== null && !inDemoArea(latitude, longitude)) {
    context.addIssue({
      code: "custom",
      path: ["latitude"],
      message: t("coordinates.validation.outOfArea"),
    })
  }
}
