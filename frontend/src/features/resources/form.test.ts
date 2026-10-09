import { describe, expect, it } from "vitest"

import i18n from "@/i18n/config"

import { parseFilters, serializeFilters, toListParams } from "./filters"
import {
  createResourceFormSchema,
  emptyResourceValues,
  resourceValuesFrom,
  toCreatePayload,
  toUpdatePayload,
} from "./form"
import type { Resource } from "./types"

const RESOURCE: Resource = {
  id: "r-1",
  code: "SIM-BOV-01",
  name: "Autobomba 1 (simulado)",
  type: {
    id: "t-1",
    code: "fire_engine",
    category: "fire",
    icon: "Truck",
    average_speed_kmh: 50,
    is_active: true,
  },
  organization: { id: "o-1", code: "sim-bov", name: "Bomberos (simulado)", is_simulated: true },
  status: "available",
  status_changed_at: "2026-10-07T08:00:00Z",
  base: { municipality: "Oviedo", description: null, latitude: 43.352, longitude: -5.873 },
  current_assignment: null,
  is_active: true,
  is_simulated: true,
  version: 3,
  created_at: "2026-10-07T08:00:00Z",
  updated_at: "2026-10-07T08:00:00Z",
}

describe("formulario de recurso", () => {
  it("el alta normaliza el código y deja el estado por defecto al backend", () => {
    expect(
      toCreatePayload({
        ...emptyResourceValues(),
        code: " bom-ovi-09 ",
        name: " Autobomba ",
        type_id: "t-1",
        organization_id: "o-1",
        municipality: " Avilés ",
      })
    ).toEqual({
      code: "BOM-OVI-09",
      name: "Autobomba",
      type_id: "t-1",
      organization_id: "o-1",
      base: { municipality: "Avilés", description: null, latitude: null, longitude: null },
      status: null,
    })
  })

  it("la edición envía solo lo que cambia con la versión, o nada", () => {
    const values = resourceValuesFrom(RESOURCE)
    expect(toUpdatePayload(values, RESOURCE)).toBeNull()
    // La base se envía completa: se conservan las coordenadas actuales.
    expect(toUpdatePayload({ ...values, municipality: "Siero" }, RESOURCE)).toEqual({
      base: { municipality: "Siero", description: null, latitude: 43.352, longitude: -5.873 },
      version: 3,
    })
    expect(toUpdatePayload({ ...values, latitude: "", longitude: "" }, RESOURCE)).toEqual({
      base: { municipality: "Oviedo", description: null, latitude: null, longitude: null },
      version: 3,
    })
  })

  it("valida el código con las mismas reglas que el backend", () => {
    const schema = createResourceFormSchema(i18n.t)
    const base = { ...resourceValuesFrom(RESOURCE) }
    for (const code of ["A", "-BOM", "BOM 01", "BOM_01", "X".repeat(33)]) {
      expect(schema.safeParse({ ...base, code }).success).toBe(false)
    }
    expect(schema.safeParse({ ...base, code: "bom-01" }).success).toBe(true)
  })

  it("valida las coordenadas de la base como en el backend", () => {
    const schema = createResourceFormSchema(i18n.t)
    const base = { ...resourceValuesFrom(RESOURCE) }
    expect(schema.safeParse({ ...base, longitude: "" }).success).toBe(false)
    expect(schema.safeParse({ ...base, latitude: "40.41", longitude: "-3.70" }).success).toBe(false)
    expect(schema.safeParse({ ...base, latitude: "", longitude: "" }).success).toBe(true)
  })
})

describe("filtros de recursos", () => {
  it("por defecto: activos por código; ida y vuelta por la URL", () => {
    expect(toListParams(parseFilters(new URLSearchParams()))).toMatchObject({
      active: true,
      sort: "code",
      offset: 0,
    })
    const search =
      "q=bomba&status=in_service&type=fire_engine&organization=o-1&inactive=1&sort=status&page=2"
    expect(serializeFilters(parseFilters(new URLSearchParams(search))).toString()).toBe(search)
  })

  it("ignora valores desconocidos", () => {
    expect(parseFilters(new URLSearchParams("status=roto&sort=nombre"))).toMatchObject({
      status: null,
      sort: "code",
    })
  })
})
