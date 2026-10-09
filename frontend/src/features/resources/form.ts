/**
 * Formulario de alta y edición de la ficha de un recurso (solo
 * `resources:manage`). Mismos límites que valida el backend
 * (schemas/resources.py). El estado operativo y la desactivación tienen sus
 * propias acciones; el código no se puede cambiar tras el alta.
 */
import type { TFunction } from "i18next"
import { z } from "zod"

import { parseCoordinate, refineCoordinates } from "@/lib/coordinates"

import type { Resource, ResourceCreate, ResourceStatus, ResourceUpdate } from "./types"

export interface ResourceFormValues {
  code: string
  name: string
  type_id: string
  organization_id: string
  /** Base del recurso: municipio, descripción y coordenadas (texto; ambas o ninguna). */
  municipality: string
  base_description: string
  latitude: string
  longitude: string
  /** Solo en el alta. `""`: disponible (valor por defecto del backend). */
  status: ResourceStatus | ""
}

export function emptyResourceValues(): ResourceFormValues {
  return {
    code: "",
    name: "",
    type_id: "",
    organization_id: "",
    municipality: "",
    base_description: "",
    latitude: "",
    longitude: "",
    status: "",
  }
}

export function resourceValuesFrom(resource: Resource): ResourceFormValues {
  return {
    code: resource.code,
    name: resource.name,
    type_id: resource.type.id,
    organization_id: resource.organization.id,
    municipality: resource.base.municipality,
    base_description: resource.base.description ?? "",
    latitude: resource.base.latitude === null ? "" : String(resource.base.latitude),
    longitude: resource.base.longitude === null ? "" : String(resource.base.longitude),
    status: "",
  }
}

// El backend normaliza a mayúsculas; aquí se acepta igual en minúsculas.
const CODE = /^[A-Za-z0-9][A-Za-z0-9-]{1,31}$/

export function createResourceFormSchema(t: TFunction) {
  return (
    z
      .object({
        code: z
          .string()
          .trim()
          .regex(CODE, { message: t("resources.validation.code") }),
        name: z
          .string()
          .trim()
          .min(1, { message: t("resources.validation.nameRequired") })
          .max(200, { message: t("resources.validation.nameTooLong") }),
        type_id: z.string().min(1, { message: t("resources.validation.typeRequired") }),
        organization_id: z
          .string()
          .min(1, { message: t("resources.validation.organizationRequired") }),
        municipality: z
          .string()
          .trim()
          .min(1, { message: t("resources.validation.municipalityRequired") })
          .max(100, { message: t("resources.validation.municipalityTooLong") }),
        base_description: z
          .string()
          .trim()
          .max(255, { message: t("resources.validation.baseDescriptionTooLong") }),
        latitude: z.string(),
        longitude: z.string(),
        status: z.union([z.literal(""), z.enum(["available", "in_service", "out_of_service"])]),
      })
      // Mismas reglas que el backend (`coordinates_incomplete`, `location_out_of_area`).
      .superRefine((values, context) => {
        refineCoordinates(values, context, t)
      }) satisfies z.ZodType<ResourceFormValues>
  )
}

function baseFrom(values: ResourceFormValues): NonNullable<ResourceUpdate["base"]> {
  return {
    municipality: values.municipality.trim(),
    description: values.base_description.trim() || null,
    latitude: parseCoordinate(values.latitude),
    longitude: parseCoordinate(values.longitude),
  }
}

export function toCreatePayload(values: ResourceFormValues): ResourceCreate {
  return {
    code: values.code.trim().toUpperCase(),
    name: values.name.trim(),
    type_id: values.type_id,
    organization_id: values.organization_id,
    base: baseFrom(values),
    status: values.status || null,
  }
}

/** Solo los campos que cambian, más `version`. `null` si no hay cambios. */
export function toUpdatePayload(
  values: ResourceFormValues,
  resource: Resource
): ResourceUpdate | null {
  const changes: Partial<ResourceUpdate> = {}
  const name = values.name.trim()
  const base = baseFrom(values)
  const current = resource.base
  if (name !== resource.name) changes.name = name
  if (values.type_id !== resource.type.id) changes.type_id = values.type_id
  if (values.organization_id !== resource.organization.id)
    changes.organization_id = values.organization_id
  // La base se envía completa (sustituye a la anterior) si cambia algo.
  if (
    base.municipality !== current.municipality ||
    (base.description ?? null) !== current.description ||
    (base.latitude ?? null) !== current.latitude ||
    (base.longitude ?? null) !== current.longitude
  )
    changes.base = base
  return Object.keys(changes).length > 0 ? { ...changes, version: resource.version } : null
}
