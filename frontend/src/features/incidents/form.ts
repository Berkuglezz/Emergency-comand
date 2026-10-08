/**
 * Formulario de alta y edición de incidentes: valores, validación y payloads.
 *
 * - Mismos límites que valida el backend (schemas/incidents.py e
 *   incident_details.py). El backend sigue siendo quien decide.
 * - `details` son secciones fijas por `details_schema_key`, no campos dinámicos
 *   (CLAUDE.md §5).
 */
import type { TFunction } from "i18next"
import { z } from "zod"

import type { IncidentCreate, IncidentDetail, IncidentPriority, IncidentUpdate } from "./types"

/** Campos de `details` de cada esquema del backend (`DETAILS_SCHEMAS`). */
export const DETAILS_FIELDS = {
  wildfire: ["affected_hectares", "vegetation"],
  flood: ["water_level_cm"],
} as const satisfies Record<string, readonly DetailsField[]>

export const VEGETATION_CODES = ["forest", "scrub", "agricultural"] as const
export type Vegetation = (typeof VEGETATION_CODES)[number]

export function isVegetation(value: unknown): value is Vegetation {
  return typeof value === "string" && (VEGETATION_CODES as readonly string[]).includes(value)
}

type DetailsField = keyof IncidentFormValues["details"]

export interface IncidentFormValues {
  type_id: string
  title: string
  /** `""`: prioridad por defecto del tipo (solo en el alta). */
  priority: IncidentPriority | ""
  municipality: string
  location_description: string
  affected_people: string
  description: string
  parent_incident_id: string
  details: { affected_hectares: string; vegetation: Vegetation | ""; water_level_cm: string }
}

export function emptyFormValues(): IncidentFormValues {
  return {
    type_id: "",
    title: "",
    priority: "",
    municipality: "",
    location_description: "",
    affected_people: "",
    description: "",
    parent_incident_id: "",
    details: { affected_hectares: "", vegetation: "", water_level_cm: "" },
  }
}

function detailText(details: Record<string, unknown>, key: string): string {
  const value = details[key]
  return typeof value === "string" || typeof value === "number" ? String(value) : ""
}

export function formValuesFromIncident(incident: IncidentDetail): IncidentFormValues {
  return {
    type_id: incident.type.id,
    title: incident.title,
    priority: incident.priority,
    municipality: incident.location.municipality,
    location_description: incident.location.description ?? "",
    affected_people: incident.affected_people === null ? "" : String(incident.affected_people),
    description: incident.description ?? "",
    parent_incident_id: incident.parent?.id ?? "",
    details: {
      affected_hectares: detailText(incident.details, "affected_hectares"),
      vegetation: isVegetation(incident.details.vegetation) ? incident.details.vegetation : "",
      water_level_cm: detailText(incident.details, "water_level_cm"),
    },
  }
}

// --- Validación -------------------------------------------------------------------

const INTEGER = /^\d+$/
const DECIMAL_2 = /^\d+([.,]\d{1,2})?$/

function optionalInteger(max: number, t: TFunction) {
  return z
    .string()
    .trim()
    .refine((value) => value === "" || (INTEGER.test(value) && Number(value) <= max), {
      message: t("incidents.validation.numberRange", { min: 0, max }),
    })
}

export function createIncidentFormSchema(t: TFunction) {
  return z.object({
    type_id: z.string().min(1, { message: t("incidents.validation.typeRequired") }),
    title: z
      .string()
      .trim()
      .min(1, { message: t("incidents.validation.titleRequired") })
      .max(200, { message: t("incidents.validation.titleTooLong") }),
    priority: z.union([z.literal(""), z.enum(["critical", "high", "medium", "low"])]),
    municipality: z
      .string()
      .trim()
      .min(1, { message: t("incidents.validation.municipalityRequired") })
      .max(100, { message: t("incidents.validation.municipalityTooLong") }),
    location_description: z
      .string()
      .trim()
      .max(255, { message: t("incidents.validation.locationTooLong") }),
    affected_people: optionalInteger(100_000, t),
    description: z
      .string()
      .trim()
      .max(5000, { message: t("incidents.validation.descriptionTooLong") }),
    parent_incident_id: z.string(),
    details: z.object({
      affected_hectares: z
        .string()
        .trim()
        .refine(
          (value) =>
            value === "" || (DECIMAL_2.test(value) && Number(value.replace(",", ".")) <= 100_000),
          { message: t("incidents.validation.decimalNumber") }
        ),
      vegetation: z.union([z.literal(""), z.enum(VEGETATION_CODES)]),
      water_level_cm: optionalInteger(2_000, t),
    }),
  }) satisfies z.ZodType<IncidentFormValues>
}

// --- Payloads ---------------------------------------------------------------------

/** `details` del tipo: solo los campos de su esquema y con valor. */
export function buildDetails(
  schemaKey: string | null | undefined,
  values: IncidentFormValues["details"]
): Record<string, unknown> {
  const fields: readonly DetailsField[] =
    schemaKey && schemaKey in DETAILS_FIELDS
      ? DETAILS_FIELDS[schemaKey as keyof typeof DETAILS_FIELDS]
      : []
  const details: Record<string, unknown> = {}
  for (const field of fields) {
    const raw = values[field].trim()
    if (!raw) continue
    if (field === "water_level_cm") details[field] = Number(raw)
    else if (field === "affected_hectares") details[field] = raw.replace(",", ".")
    else details[field] = raw
  }
  return details
}

/** Igualdad de `details` sin depender del orden de las claves. */
function sameDetails(a: Record<string, unknown>, b: Record<string, unknown>): boolean {
  const keys = Object.keys(a)
  return (
    keys.length === Object.keys(b).length &&
    keys.every((key) => key in b && String(a[key]) === String(b[key]))
  )
}

const optionalText = (value: string) => value.trim() || null
const optionalNumber = (value: string) => (value.trim() === "" ? null : Number(value))

export function toCreatePayload(
  values: IncidentFormValues,
  schemaKey: string | null | undefined
): IncidentCreate {
  return {
    type_id: values.type_id,
    title: values.title.trim(),
    priority: values.priority || null,
    location: {
      municipality: values.municipality.trim(),
      description: optionalText(values.location_description),
    },
    affected_people: optionalNumber(values.affected_people),
    description: optionalText(values.description),
    details: buildDetails(schemaKey, values.details),
    parent_incident_id: values.parent_incident_id || null,
  }
}

/**
 * Edición parcial: solo los campos que cambian, más `version` (bloqueo
 * optimista). Devuelve `null` si no hay cambios: no se llama a la API.
 */
export function toUpdatePayload(
  values: IncidentFormValues,
  incident: IncidentDetail,
  schemaKey: string | null | undefined
): IncidentUpdate | null {
  const next = toCreatePayload(values, schemaKey)
  const changes: Partial<IncidentUpdate> = {}

  if (next.title !== incident.title) changes.title = next.title
  if (next.priority && next.priority !== incident.priority) changes.priority = next.priority
  // La ubicación se envía completa: sustituye a la anterior. El formulario aún
  // no edita coordenadas, así que se reenvían las actuales para no borrarlas.
  if (
    next.location.municipality !== incident.location.municipality ||
    (next.location.description ?? null) !== incident.location.description
  )
    changes.location = {
      ...next.location,
      latitude: incident.location.latitude,
      longitude: incident.location.longitude,
    }
  // Vaciar un texto opcional se envía como "" (el backend lo guarda como nulo).
  if (next.description !== incident.description) changes.description = next.description ?? ""
  if (next.affected_people !== incident.affected_people)
    changes.affected_people = next.affected_people
  if (next.parent_incident_id !== (incident.parent?.id ?? null))
    changes.parent_incident_id = next.parent_incident_id
  const details = next.details ?? {}
  if (!sameDetails(details, incident.details)) changes.details = details

  return Object.keys(changes).length > 0 ? { ...changes, version: incident.version } : null
}
