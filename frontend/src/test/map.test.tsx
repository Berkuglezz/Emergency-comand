/**
 * Mapa (Fase 3) con el backend falso y el doble de MapLibre: marcadores,
 * selección mapa ↔ lista ↔ panel, filtros compartidos, incidentes sin
 * coordenadas, fallos del mapa base y coordenadas en formulario y ficha.
 */
import { act, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { type FakeBackend, installFakeBackend } from "./fake-backend"
import { Map as FakeMap } from "./fake-maplibre"
import { renderApp } from "./render-app"

let backend: FakeBackend

beforeEach(() => {
  backend = installFakeBackend()
})

const OVIEDO = { latitude: 43.361, longitude: -5.844 }
const GIJON = { latitude: 43.535, longitude: -5.637 }

function seed(): void {
  backend.incidents.add({ title: "Incendio", priority: "critical", coordinates: OVIEDO })
  backend.incidents.add({
    title: "Inundación",
    priority: "high",
    status: "in_progress",
    coordinates: GIJON,
  })
  backend.incidents.add({ title: "Aviso sin posición", priority: "medium" })
  backend.incidents.add({ title: "Cerrado", priority: "low", status: "closed", coordinates: GIJON })
}

// El mapa es un chunk diferido: la primera carga en frío puede pasar de 1 s.
const LAZY_TIMEOUT = { timeout: 5000 }

async function mapRegion(): Promise<HTMLElement> {
  return screen.findByRole("region", { name: "Mapa de incidentes activos" }, LAZY_TIMEOUT)
}

function lastMap(): FakeMap {
  const map = FakeMap.instances.at(-1)
  if (!map) throw new Error("sin mapa")
  return map
}

describe("mapa del centro de mando", () => {
  it("dibuja los incidentes activos con coordenadas y cuenta los que no tienen", async () => {
    seed()
    backend.startSessionFor("operator")
    renderApp("/")

    const map = await mapRegion()
    const markers = await within(map).findAllByRole("button", { name: /^INC-/ })
    expect(markers.map((marker) => marker.getAttribute("aria-label"))).toEqual([
      "INC-000001, prioridad Crítica, Recibido, Simulado",
      "INC-000002, prioridad Alta, En intervención, Simulado",
    ])
    // Borde por estado: discontinuo sin intervenir, continuo en intervención.
    expect(markers[0]).toHaveClass("border-dashed")
    expect(markers[1]).toHaveClass("border-solid")
    expect(screen.getByText("2 incidentes en el mapa")).toBeInTheDocument()
    expect(screen.getByText("Datos simulados")).toBeInTheDocument()
    expect(screen.getByText("1 incidente activo sin coordenadas.")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Ver en el listado" })).toHaveAttribute(
      "href",
      "/incidents?coords=without"
    )
    // Atribución obligatoria, siempre visible.
    expect(screen.getByRole("link", { name: "OpenFreeMap" })).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Datos © colaboradores de OpenStreetMap" })
    ).toBeInTheDocument()
  })

  it("seleccionar en el mapa abre el panel lateral y resalta la fila", async () => {
    seed()
    backend.startSessionFor("operator")
    const { user, router } = renderApp("/")
    const incendio = backend.incidents.byCode("INC-000001")

    await user.click(await within(await mapRegion()).findByRole("button", { name: /^INC-000001/ }))

    expect(router.state.location.search).toBe(`?incident=${incendio.id}`)
    expect(await screen.findByRole("heading", { name: "Incendio" })).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Ver INC-000001 en el panel lateral" })
    ).toHaveAttribute("aria-pressed", "true")
    expect(within(await mapRegion()).getByRole("button", { name: /^INC-000001/ })).toHaveAttribute(
      "aria-pressed",
      "true"
    )
  })

  it("seleccionar en la lista centra el mapa si el incidente no está a la vista", async () => {
    seed()
    backend.startSessionFor("operator")
    const { user } = renderApp("/")
    await within(await mapRegion()).findAllByRole("button", { name: /^INC-/ })
    // Vista alejada de Gijón.
    lastMap().visible = [
      [-6.5, 43.0],
      [-6.0, 43.2],
    ]

    await user.click(screen.getByRole("button", { name: "Ver INC-000002 en el panel lateral" }))

    await waitFor(() => {
      expect(lastMap().calls).toContainEqual({
        method: "easeTo",
        args: [{ center: [GIJON.longitude, GIJON.latitude], animate: true }],
      })
    })
  })

  it("con movimiento reducido centra sin animación y no mueve si ya está a la vista", async () => {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("reduce") }))
    seed()
    backend.startSessionFor("operator")
    const { user } = renderApp("/")
    await within(await mapRegion()).findAllByRole("button", { name: /^INC-/ })

    // Oviedo está dentro de la vista inicial (Asturias): no se mueve.
    await user.click(screen.getByRole("button", { name: "Ver INC-000001 en el panel lateral" }))
    await screen.findByRole("heading", { name: "Incendio" })
    expect(lastMap().calls.filter((call) => call.method === "easeTo")).toEqual([])

    lastMap().visible = [
      [-6.5, 43.0],
      [-6.0, 43.2],
    ]
    await user.click(screen.getByRole("button", { name: "Ver INC-000002 en el panel lateral" }))
    await waitFor(() => {
      expect(lastMap().calls).toContainEqual({
        method: "easeTo",
        args: [{ center: [GIJON.longitude, GIJON.latitude], animate: false }],
      })
    })
  })

  it("aplica los mismos filtros que la lista", async () => {
    seed()
    backend.startSessionFor("operator")
    const { user } = renderApp("/")
    const map = await mapRegion()
    await within(map).findAllByRole("button", { name: /^INC-/ })

    const list = screen.getByRole("heading", { name: "Incidentes activos" }).closest("section")
    if (!list) throw new Error("lista")
    await user.selectOptions(within(list).getByLabelText("Prioridad"), "critical")

    await waitFor(() => {
      expect(within(map).getAllByRole("button", { name: /^INC-/ })).toHaveLength(1)
    })
    expect(within(map).getByRole("button", { name: /^INC-000001/ })).toBeInTheDocument()
    expect(screen.queryByText(/sin coordenadas\./)).not.toBeInTheDocument()
  })

  it("avisa si el incidente seleccionado no tiene coordenadas", async () => {
    seed()
    const sinPosicion = backend.incidents.byCode("INC-000003")
    backend.startSessionFor("operator")
    renderApp(`/?incident=${sinPosicion.id}`)

    expect(
      await screen.findByText("INC-000003 no tiene coordenadas: no aparece en el mapa.")
    ).toBeInTheDocument()
    // En el panel lateral y en la lista también se indica.
    expect(screen.getAllByText("Sin coordenadas").length).toBeGreaterThan(0)
  })

  it("los botones de encuadre ajustan a los incidentes o a Asturias", async () => {
    seed()
    backend.startSessionFor("operator")
    const { user } = renderApp("/")
    await within(await mapRegion()).findAllByRole("button", { name: /^INC-/ })

    await user.click(screen.getByRole("button", { name: "Ajustar a incidentes" }))
    await user.click(screen.getByRole("button", { name: "Centrar en Asturias" }))

    const fits = lastMap().calls.filter((call) => call.method === "fitBounds")
    expect(fits.map((call) => call.args[0])).toEqual([
      // Oviedo queda al oeste y al sur; Gijón, al este y al norte.
      [
        [OVIEDO.longitude, OVIEDO.latitude],
        [GIJON.longitude, GIJON.latitude],
      ],
      [
        [-7.2, 42.85],
        [-4.5, 43.7],
      ],
    ])
  })

  it("sin mapa base sigue mostrando las posiciones", async () => {
    FakeMap.mode = "basemap_error"
    seed()
    backend.startSessionFor("operator")
    renderApp("/")

    expect(await screen.findByText("Cartografía no disponible")).toBeInTheDocument()
    expect(within(await mapRegion()).getAllByRole("button", { name: /^INC-/ })).toHaveLength(2)
  })

  it("si el navegador no puede crear el mapa, la lista sigue funcionando", async () => {
    FakeMap.mode = "unsupported"
    seed()
    backend.startSessionFor("operator")
    renderApp("/")

    expect(await screen.findByText("Mapa no disponible")).toBeInTheDocument()
    expect(
      await screen.findByRole("button", { name: "Ver INC-000001 en el panel lateral" })
    ).toBeInTheDocument()
  })
})

describe("coordenadas en el listado, la ficha y el formulario", () => {
  it("el listado filtra por coordenadas desde la URL", async () => {
    seed()
    backend.startSessionFor("operator")
    renderApp("/incidents?coords=without")

    expect(await screen.findByRole("link", { name: "INC-000003" })).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: "INC-000001" })).not.toBeInTheDocument()
    const call = backend.calls.findLast((c) => c.method === "GET" && c.path === "/incidents")
    expect(call?.query.get("has_coordinates")).toBe("false")
  })

  it("la ficha muestra el minimapa con las coordenadas, o que no las tiene", async () => {
    seed()
    const incendio = backend.incidents.byCode("INC-000001")
    const sinPosicion = backend.incidents.byCode("INC-000003")
    backend.startSessionFor("operator")
    const { router } = renderApp(`/incidents/${incendio.id}`)

    expect(
      await screen.findByRole(
        "region",
        { name: "Mapa de la ubicación de INC-000001" },
        LAZY_TIMEOUT
      )
    ).toBeInTheDocument()
    expect(screen.getByText("43.361, -5.844")).toBeInTheDocument()

    await act(() => router.navigate(`/incidents/${sinPosicion.id}`))
    expect(await screen.findByText("Se pueden añadir al editar el incidente.")).toBeInTheDocument()
  })

  it("elegir en el mapa rellena las coordenadas del alta", async () => {
    backend.startSessionFor("coordinator")
    const { user } = renderApp("/incidents/new")

    await user.selectOptions(await screen.findByLabelText("Tipo de incidente"), "Incendio forestal")
    await user.type(screen.getByLabelText("Título"), "Con posición")
    await user.type(screen.getByLabelText("Municipio"), "Siero")
    await user.click(screen.getByRole("button", { name: "Elegir en el mapa" }))

    const dialog = await screen.findByRole("dialog")
    await within(dialog).findByRole(
      "region",
      { name: "Mapa para elegir la posición" },
      LAZY_TIMEOUT
    )
    act(() => {
      lastMap().fire("click", { lngLat: { lng: -5.6100004, lat: 43.3600004 } })
    })
    expect(await within(dialog).findByText("43.36, -5.61")).toBeInTheDocument()
    await user.click(within(dialog).getByRole("button", { name: "Usar esta posición" }))

    expect(screen.getByLabelText("Latitud")).toHaveValue("43.36")
    expect(screen.getByLabelText("Longitud")).toHaveValue("-5.61")
    await user.click(screen.getByRole("button", { name: "Registrar incidente" }))

    await screen.findByRole("heading", { name: "Con posición" })
    const post = backend.calls.find((call) => call.method === "POST" && call.path === "/incidents")
    expect(post?.body).toMatchObject({
      location: { municipality: "Siero", latitude: 43.36, longitude: -5.61 },
    })
  })

  it("el selector no deja confirmar una posición fuera de Asturias", async () => {
    backend.startSessionFor("coordinator")
    const { user } = renderApp("/incidents/new")

    await user.click(await screen.findByRole("button", { name: "Elegir en el mapa" }))
    const dialog = await screen.findByRole("dialog")
    await within(dialog).findByRole(
      "region",
      { name: "Mapa para elegir la posición" },
      LAZY_TIMEOUT
    )
    act(() => {
      lastMap().fire("click", { lngLat: { lng: -3.7038, lat: 40.4168 } })
    })

    expect(
      await within(dialog).findByText(/fuera del área de la demo \(Asturias\)/)
    ).toBeInTheDocument()
    expect(within(dialog).getByRole("button", { name: "Usar esta posición" })).toBeDisabled()
  })

  it("el historial muestra el antes y el después de un cambio de ubicación", async () => {
    const incident = backend.incidents.add({ title: "Móvil", coordinates: OVIEDO })
    backend.startSessionFor("coordinator")
    const { user } = renderApp(`/incidents/${incident.id}`)
    await screen.findByRole("heading", { name: "Móvil" })

    await user.click(screen.getByRole("button", { name: "Editar" }))
    const latitude = screen.getByLabelText("Latitud")
    await user.clear(latitude)
    await user.type(latitude, "43.4")
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    expect(await screen.findByText("Ubicación cambiada: coordenadas")).toBeInTheDocument()
    expect(
      screen.getByText(/Antes: Oviedo · 43\.361, -5\.844\s+Ahora: Oviedo · 43\.4, -5\.844/)
    ).toBeInTheDocument()
  })
})
