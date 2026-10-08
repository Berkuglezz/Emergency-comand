import { describe, expect, it } from "vitest"

import i18n from "@/i18n/config"

import {
  buildDetails,
  createIncidentFormSchema,
  emptyFormValues,
  formValuesFromIncident,
  type IncidentFormValues,
  toCreatePayload,
  toUpdatePayload,
} from "./form"
import type { IncidentDetail } from "./types"

const INCIDENT: IncidentDetail = {
  id: "i-1",
  code: "INC-000001",
  title: "Incendio",
  status: "in_progress",
  priority: "high",
  type: { id: "t-1", code: "wildfire", category: "fire", icon: "Flame" },
  location: {
    municipality: "Siero",
    description: "Zona forestal (ubicación simulada)",
    latitude: 43.39,
    longitude: -5.66,
  },
  affected_people: null,
  parent_incident_id: null,
  is_simulated: true,
  version: 4,
  reported_at: "2026-10-07T08:00:00Z",
  updated_at: "2026-10-07T09:00:00Z",
  description: null,
  details: { affected_hectares: "12.50", vegetation: "forest" },
  parent: null,
  children: [],
  closed_at: null,
  created_at: "2026-10-07T08:00:00Z",
  allowed_transitions: ["controlled", "cancelled"],
}

function values(changes: Partial<IncidentFormValues>): IncidentFormValues {
  return { ...formValuesFromIncident(INCIDENT), ...changes }
}

describe("details por tipo", () => {
  it("solo incluye los campos del esquema del tipo y con valor", () => {
    const details = { affected_hectares: "3,5", vegetation: "" as const, water_level_cm: "40" }
    expect(buildDetails("wildfire", details)).toEqual({ affected_hectares: "3.5" })
    expect(buildDetails("flood", details)).toEqual({ water_level_cm: 40 })
    // Un tipo sin esquema exige `details = {}`.
    expect(buildDetails(null, details)).toEqual({})
  })
})

describe("alta", () => {
  it("convierte vacíos en nulos y deja la prioridad al tipo si no se elige", () => {
    const payload = toCreatePayload(
      { ...emptyFormValues(), type_id: "t-2", title: "  Colisión ", municipality: "Gijón" },
      null
    )
    expect(payload).toEqual({
      type_id: "t-2",
      title: "Colisión",
      priority: null,
      location: { municipality: "Gijón", description: null },
      affected_people: null,
      description: null,
      details: {},
      parent_incident_id: null,
    })
  })
})

describe("edición", () => {
  it("sin cambios devuelve null: no se llama a la API", () => {
    expect(toUpdatePayload(values({}), INCIDENT, "wildfire")).toBeNull()
  })

  it("envía solo lo que cambia, con la versión", () => {
    const payload = toUpdatePayload(
      values({ title: "Incendio controlado", priority: "critical" }),
      INCIDENT,
      "wildfire"
    )
    expect(payload).toEqual({ title: "Incendio controlado", priority: "critical", version: 4 })
  })

  it("vaciar un texto opcional se envía como cadena vacía", () => {
    const payload = toUpdatePayload(values({ description: "Notas" }), INCIDENT, "wildfire")
    expect(payload).toEqual({ description: "Notas", version: 4 })
    const cleared = toUpdatePayload(
      values({ description: "" }),
      { ...INCIDENT, description: "Notas" },
      "wildfire"
    )
    expect(cleared).toEqual({ description: "", version: 4 })
  })

  it("la ubicación se envía completa, conservando las coordenadas actuales", () => {
    expect(toUpdatePayload(values({ location_description: "" }), INCIDENT, "wildfire")).toEqual({
      location: { municipality: "Siero", description: null, latitude: 43.39, longitude: -5.66 },
      version: 4,
    })
    expect(toUpdatePayload(values({ municipality: "Gijón" }), INCIDENT, "wildfire")).toEqual({
      location: {
        municipality: "Gijón",
        description: "Zona forestal (ubicación simulada)",
        latitude: 43.39,
        longitude: -5.66,
      },
      version: 4,
    })
  })

  it("detecta cambios en details sin depender del orden de las claves", () => {
    expect(
      toUpdatePayload(
        values({
          details: { affected_hectares: "12.50", vegetation: "scrub", water_level_cm: "" },
        }),
        INCIDENT,
        "wildfire"
      )
    ).toEqual({ details: { affected_hectares: "12.50", vegetation: "scrub" }, version: 4 })
  })
})

describe("validación", () => {
  const schema = createIncidentFormSchema(i18n.t)

  it("aplica los mismos límites que el backend", () => {
    const result = schema.safeParse({
      ...emptyFormValues(),
      title: "x".repeat(201),
      affected_people: "100001",
      details: { affected_hectares: "1.234", vegetation: "", water_level_cm: "2001" },
    })
    expect(result.success).toBe(false)
    const paths = result.error?.issues.map((issue) => issue.path.join(".")).sort()
    expect(paths).toEqual([
      "affected_people",
      "details.affected_hectares",
      "details.water_level_cm",
      "municipality",
      "title",
      "type_id",
    ])
  })
})
