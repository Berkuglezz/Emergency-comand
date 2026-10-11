/**
 * Mapa operativo, M.2 (CLAUDE.md §2.12): perímetros guardados del incidente
 * seleccionado, en el mapa (capa GeoJSON del doble de MapLibre) y en la lista
 * de solo lectura del panel lateral. Nada se crea ni se modifica.
 */
import { act, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import { type FakeBackend, installFakeBackend } from "./fake-backend"
import { Map as FakeMap } from "./fake-maplibre"
import { renderApp } from "./render-app"

let backend: FakeBackend

beforeEach(() => {
  backend = installFakeBackend()
})

const OVIEDO = { latitude: 43.361, longitude: -5.844 }
const GIJON = { latitude: 43.535, longitude: -5.637 }
const RING: [number, number][] = [
  [-5.86, 43.35],
  [-5.83, 43.35],
  [-5.83, 43.37],
  [-5.86, 43.37],
  [-5.86, 43.35],
]

/** Incendio (INC-000001) con perímetro e inundación (INC-000002) sin él. */
function seed() {
  const fire = backend.incidents.add({
    title: "Incendio",
    priority: "critical",
    coordinates: OVIEDO,
  })
  const flood = backend.incidents.add({ title: "Inundación", priority: "high", coordinates: GIJON })
  const perimeter = backend.incidents.addPerimeter(fire.id, {
    ring: RING,
    label: "Frente norte",
    note: "Estimado desde el puesto de mando",
  })
  // Retirado: no se representa (la consulta pide solo los activos).
  backend.incidents.addPerimeter(fire.id, { ring: RING, label: "Anterior", status: "retired" })
  return { fire, flood, perimeter }
}

function lastMap(): FakeMap {
  const map = FakeMap.instances.at(-1)
  if (!map) throw new Error("sin mapa")
  return map
}

/** Ids de los elementos que la capa de perímetros está dibujando ahora. */
function drawnIds(): string[] | undefined {
  const data = lastMap().sources.get("ec-perimeters")?.data as
    { features: { properties: { id: string } }[] } | undefined
  return data?.features.map((feature) => feature.properties.id)
}

/** Indicador del mapa (la leyenda, plegada, repite el mismo texto). */
function perimeterPill(): HTMLElement | undefined {
  return screen
    .queryAllByText("Perímetro · Dibujado · no validado")
    .find((element) => !element.closest("details"))
}

async function mapRegion(): Promise<HTMLElement> {
  return screen.findByRole("region", { name: "Mapa de incidentes activos" })
}

describe("perímetros del incidente seleccionado (M.2)", () => {
  it("se dibujan en el mapa con contorno discontinuo y se listan como no validados", async () => {
    const { fire, perimeter } = seed()
    backend.startSessionFor("coordinator")
    renderApp(`/?incident=${fire.id}`)

    await waitFor(() => {
      expect(drawnIds()).toEqual([perimeter.id])
    })
    const map = lastMap()
    expect(map.layers.map((layer) => [layer.id, layer.type])).toEqual([
      ["ec-perimeters-fill", "fill"],
      ["ec-perimeters-line", "line"],
    ])
    expect(map.layers[1]?.paint).toMatchObject({ "line-dasharray": [2, 1.5] })
    expect(perimeterPill()).toHaveAttribute("data-tone", "warning")

    // Los marcadores siguen ahí, por encima de la capa.
    expect(within(await mapRegion()).getAllByRole("button", { name: /^INC-/ })).toHaveLength(2)

    const list = await screen.findByRole("region", { name: "Perímetros" })
    expect(await within(list).findByText("Frente norte")).toBeInTheDocument()
    expect(within(list).getByText("Dibujado · no validado")).toBeInTheDocument()
    expect(within(list).getByText("Estimado desde el puesto de mando")).toBeInTheDocument()
    expect(within(list).getByText(/Última modificación: Usuario coordinator/)).toBeInTheDocument()
    expect(within(list).queryByText("Anterior")).not.toBeInTheDocument()
    // Solo lectura: ni siquiera coordinación tiene acciones aquí.
    expect(within(list).queryByRole("button")).not.toBeInTheDocument()
  })

  it("la leyenda explica el trazo del perímetro", async () => {
    seed()
    backend.startSessionFor("operator")
    const { user } = renderApp("/")

    await user.click(await screen.findByText("Leyenda"))
    const legend = screen.getByRole("list", { name: "Mapa operativo" })
    expect(within(legend).getByText("Perímetro · Dibujado · no validado")).toBeVisible()
  })

  it("sin incidente seleccionado no se consulta nada", async () => {
    seed()
    backend.startSessionFor("operator")
    renderApp("/")

    await within(await mapRegion()).findAllByRole("button", { name: /^INC-/ })
    expect(backend.calls.filter((call) => call.path.endsWith("/map-features"))).toEqual([])
    expect(drawnIds()).toEqual([])
  })

  it("un incidente sin perímetro lo indica en el panel y no dibuja nada", async () => {
    const { flood } = seed()
    backend.startSessionFor("operator")
    renderApp(`/?incident=${flood.id}`)

    const list = await screen.findByRole("region", { name: "Perímetros" })
    expect(
      await within(list).findByText("Este incidente no tiene ningún perímetro dibujado.")
    ).toBeInTheDocument()
    expect(drawnIds()).toEqual([])
    expect(perimeterPill()).toBeUndefined()
  })

  it("al cambiar de incidente nunca queda el perímetro del anterior", async () => {
    const { fire, perimeter } = seed()
    backend.startSessionFor("operator")
    const { user } = renderApp(`/?incident=${fire.id}`)
    await waitFor(() => {
      expect(drawnIds()).toEqual([perimeter.id])
    })

    // La respuesta del nuevo incidente se retrasa: mientras tanto, nada dibujado.
    let release: () => void = () => undefined
    backend.holdMapFeatures = new Promise<void>((resolve) => {
      release = resolve
    })
    await user.click(screen.getByRole("button", { name: "Ver INC-000002 en el panel lateral" }))
    expect(await screen.findByText("Cargando perímetro…")).toBeInTheDocument()
    expect(drawnIds()).toEqual([])
    expect(screen.queryByText("Frente norte")).not.toBeInTheDocument()

    act(() => {
      release()
    })
    expect(
      await screen.findByText("Este incidente no tiene ningún perímetro dibujado.")
    ).toBeInTheDocument()
    expect(screen.queryByText("Cargando perímetro…")).not.toBeInTheDocument()
    expect(drawnIds()).toEqual([])

    // Volver al primero lo dibuja de nuevo.
    backend.holdMapFeatures = null
    await user.click(screen.getByRole("button", { name: "Ver INC-000001 en el panel lateral" }))
    await waitFor(() => {
      expect(drawnIds()).toEqual([perimeter.id])
    })
  })

  it("si la consulta falla avisa sin ocultar los incidentes y se puede reintentar", async () => {
    const { fire, perimeter } = seed()
    backend.incidents.failMapFeatures = true
    backend.startSessionFor("operator")
    const { user } = renderApp(`/?incident=${fire.id}`, { retry: false })

    expect(await screen.findByText("No se pudo cargar el perímetro.")).toBeInTheDocument()
    expect(within(await mapRegion()).getAllByRole("button", { name: /^INC-/ })).toHaveLength(2)
    const list = screen.getByRole("region", { name: "Perímetros" })
    expect(await within(list).findByRole("alert")).toBeInTheDocument()
    expect(drawnIds()).toEqual([])

    backend.incidents.failMapFeatures = false
    const notice = screen.getByText("No se pudo cargar el perímetro.")
    await user.click(within(notice).getByRole("button", { name: "Reintentar" }))
    await waitFor(() => {
      expect(drawnIds()).toEqual([perimeter.id])
    })
    expect(screen.queryByText("No se pudo cargar el perímetro.")).not.toBeInTheDocument()
    expect(await within(list).findByText("Frente norte")).toBeInTheDocument()
  })

  it("sin mapa base no se puede dibujar, pero el perímetro sigue en el panel", async () => {
    FakeMap.mode = "basemap_error"
    const { fire } = seed()
    backend.startSessionFor("operator")
    renderApp(`/?incident=${fire.id}`)

    expect(
      await screen.findByText(
        "Sin cartografía no se puede dibujar el perímetro: consúltalo en el panel lateral."
      )
    ).toBeInTheDocument()
    expect(lastMap().layers).toEqual([])
    const list = screen.getByRole("region", { name: "Perímetros" })
    expect(await within(list).findByText("Frente norte")).toBeInTheDocument()
  })

  it("«Ajustar a incidentes» incluye el perímetro", async () => {
    const { fire } = seed()
    backend.startSessionFor("operator")
    const { user } = renderApp(`/?incident=${fire.id}`)
    await waitFor(() => {
      expect(perimeterPill()).toBeDefined()
    })

    await user.click(screen.getByRole("button", { name: "Ajustar a incidentes" }))
    const fit = lastMap().calls.findLast((call) => call.method === "fitBounds")
    // El perímetro sobresale al oeste y al sur de Oviedo.
    expect(fit?.args[0]).toEqual([
      [-5.86, 43.35],
      [GIJON.longitude, GIJON.latitude],
    ])
  })

  it("solo lee: ninguna petición escribe elementos del mapa", async () => {
    const { fire, flood } = seed()
    backend.startSessionFor("coordinator")
    const { user } = renderApp(`/?incident=${fire.id}`)
    await screen.findByText("Frente norte")
    await user.click(screen.getByRole("button", { name: "Ver INC-000002 en el panel lateral" }))
    await screen.findByText("Este incidente no tiene ningún perímetro dibujado.")

    // Mapa y panel comparten la consulta; pueden pedirla al montar, pero siempre con GET.
    const calls = backend.calls.filter((call) => call.path.includes("map-features"))
    expect(new Set(calls.map((call) => `${call.method} ${call.path}`))).toEqual(
      new Set([`GET /incidents/${fire.id}/map-features`, `GET /incidents/${flood.id}/map-features`])
    )
  })
})
