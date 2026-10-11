/**
 * Texto de cada entrada del historial: los eventos existentes se representan
 * igual que siempre, los de los elementos del mapa (M.1) tienen su texto y un
 * tipo desconocido nunca rompe la ficha.
 */
import { render } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { TimelineEntry } from "./components/incident-timeline"
import type { IncidentEvent } from "./types"

/** Texto principal y detalle (con sus saltos de línea) de una entrada. */
function renderEntry(eventType: string, payload: Record<string, unknown>) {
  // `as`: también se prueban tipos futuros que llegan de la API fuera del
  // contrato de los tipos generados.
  const event = {
    id: "30000000-0000-4000-8000-000000000001",
    event_type: eventType as IncidentEvent["event_type"],
    occurred_at: "2026-10-09T10:00:00Z",
    actor: { id: "10000000-0000-4000-8000-000000000001", full_name: "Coordinación Demo" },
    payload,
    is_simulated: true,
  } satisfies IncidentEvent
  const { container } = render(
    <ol>
      <TimelineEntry event={event} />
    </ol>
  )
  const [text, detail] = Array.from(container.querySelectorAll("p"), (p) => p.textContent)
  return { text, detail: detail ?? null, icon: container.querySelector("svg") }
}

describe("historial: eventos existentes", () => {
  it.each<[string, Record<string, unknown>, string, string | null]>([
    ["incident_created", { priority: "high" }, "Incidente registrado con prioridad Alta", null],
    [
      "incident_created",
      { priority: "critical", parent: "INC-000001" },
      "Incidente registrado con prioridad Crítica, agrupado en INC-000001",
      null,
    ],
    [
      "status_changed",
      { from: "received", to: "assessing", reason: "Revisión" },
      "Estado: Recibido → En valoración",
      "Motivo: Revisión",
    ],
    [
      "status_changed",
      { from: "assessing", to: "resources_assigned", cause: "assignment" },
      "Estado: En valoración → Recursos asignados",
      "Automático por la asignación de recursos",
    ],
    ["priority_changed", { from: "low", to: "high" }, "Prioridad: Baja → Alta", null],
    [
      "incident_updated",
      { fields: ["title", "affected_people"] },
      "Datos modificados: título, personas afectadas",
      null,
    ],
    [
      "location_changed",
      {
        fields: ["municipality", "coordinates"],
        from: { municipality: "Oviedo", description: null, latitude: null, longitude: null },
        to: { municipality: "Siero", description: "Polígono", latitude: 43.39, longitude: -5.66 },
      },
      "Ubicación cambiada: municipio, coordenadas",
      "Antes: Oviedo · Sin coordenadas\nAhora: Siero · Polígono · 43.39, -5.66",
    ],
    ["note_added", { text: "Zona señalizada" }, "Nota", "Zona señalizada"],
    ["parent_changed", { from: null, to: "INC-000002" }, "Agrupado en INC-000002", null],
    ["parent_changed", { from: "INC-000002", to: null }, "Separado de INC-000002", null],
    [
      "parent_changed",
      { from: "INC-000002", to: "INC-000003" },
      "Movido de INC-000002 a INC-000003",
      null,
    ],
    [
      "resource_assigned",
      { resource: "BOM-01", eta: { minutes: 12, distance_km: 8.4 }, reassigned_from: "INC-000003" },
      "Recurso asignado: BOM-01",
      "ETA estimada: ≈ 12 min · 8,4 km\nReasignado desde INC-000003",
    ],
    [
      "resource_assigned",
      { resource: "BOM-01", eta: null },
      "Recurso asignado: BOM-01",
      "Sin ETA estimada",
    ],
    ["resource_arrived", { resource: "BOM-01" }, "BOM-01 en el lugar", null],
    [
      "resource_released",
      { resource: "BOM-01", reason: "completed", reassigned_to: null },
      "Recurso retirado: BOM-01",
      "Misión cumplida",
    ],
    [
      "resource_released",
      { resource: "BOM-01", reason: "reassigned", reassigned_to: "INC-000004" },
      "Recurso retirado: BOM-01",
      "Reasignado a otro incidente\nReasignado a INC-000004",
    ],
  ])("%s %j", (eventType, payload, text, detail) => {
    const entry = renderEntry(eventType, payload)
    expect(entry.text).toBe(text)
    expect(entry.detail).toBe(detail)
    expect(entry.icon).not.toBeNull()
  })
})

describe("historial: elementos del mapa y tipos sin representación propia", () => {
  const polygon = {
    type: "Polygon",
    coordinates: [
      [
        [-5.85, 43.36],
        [-5.84, 43.36],
        [-5.84, 43.37],
        [-5.85, 43.36],
      ],
    ],
  }

  it("map_feature_added: tipo y etiqueta, sin mostrar la geometría", () => {
    const entry = renderEntry("map_feature_added", {
      feature_id: "40000000-0000-4000-8000-000000000001",
      kind: "perimeter",
      label: "Frente norte",
      before: null,
      after: polygon,
    })
    expect(entry.text).toBe("Elemento del mapa añadido: perímetro")
    expect(entry.detail).toBe("Etiqueta: Frente norte")
    expect(entry.icon).not.toBeNull()
  })

  it("map_feature_added sin etiqueta: sin detalle", () => {
    const entry = renderEntry("map_feature_added", {
      kind: "perimeter",
      label: null,
      before: null,
      after: polygon,
    })
    expect(entry.text).toBe("Elemento del mapa añadido: perímetro")
    expect(entry.detail).toBeNull()
  })

  it("map_feature_updated: campos cambiados", () => {
    const entry = renderEntry("map_feature_updated", {
      kind: "perimeter",
      label: "Frente norte",
      before: polygon,
      after: polygon,
      fields: ["geometry", "label"],
    })
    expect(entry.text).toBe("Elemento del mapa modificado: perímetro")
    expect(entry.detail).toBe("Etiqueta: Frente norte\nCambios: geometría, etiqueta")
  })

  it("map_feature_retired: motivo", () => {
    const entry = renderEntry("map_feature_retired", {
      kind: "perimeter",
      label: null,
      before: polygon,
      after: null,
      reason: "Perímetro sustituido",
    })
    expect(entry.text).toBe("Elemento del mapa retirado: perímetro")
    expect(entry.detail).toBe("Motivo: Perímetro sustituido")
  })

  it("un payload incompleto o un tipo de elemento desconocido no rompe la entrada", () => {
    expect(renderEntry("map_feature_updated", {}).text).toBe("Elemento del mapa modificado: —")
    expect(renderEntry("map_feature_added", { kind: "new_kind" }).text).toBe(
      "Elemento del mapa añadido: new_kind"
    )
  })

  it("un tipo de evento desconocido se muestra de forma genérica, con icono", () => {
    const entry = renderEntry("future_event", { anything: 1 })
    expect(entry.text).toBe("Evento registrado (future_event)")
    expect(entry.detail).toBeNull()
    expect(entry.icon).not.toBeNull()
  })
})
