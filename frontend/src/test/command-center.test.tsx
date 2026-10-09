/**
 * Centro de mando con datos reales del backend falso: KPIs, incidentes activos
 * con filtros y selección, panel lateral y resumen de recursos. El mapa se
 * prueba en `map.test.tsx`.
 */
import { screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import { type FakeBackend, installFakeBackend } from "./fake-backend"
import { renderApp } from "./render-app"

let backend: FakeBackend

beforeEach(() => {
  backend = installFakeBackend()
})

/** Valor mostrado en un KPI (la tarjeta contiene etiqueta y cifra). */
async function kpi(label: string): Promise<HTMLElement> {
  const kpis = await screen.findByRole("region", { name: "Indicadores" })
  const tile = within(kpis).getByText(label).closest("[data-state]")
  if (!(tile instanceof HTMLElement)) throw new Error(label)
  return tile
}

function seed(): void {
  const storm = backend.incidents.add({
    title: "Temporal",
    priority: "high",
    status: "in_progress",
  })
  backend.incidents.add({ title: "Incendio crítico", priority: "critical", typeCode: "wildfire" })
  backend.incidents.add({ title: "Inundación hija", priority: "medium", parentCode: storm.code })
  backend.incidents.add({ title: "Ya cerrado", priority: "low", status: "closed" })
  backend.resources.add({ code: "SIM-A-01" })
  backend.resources.add({ code: "SIM-A-02" })
  backend.resources.add({ code: "SIM-A-03", status: "in_service" })
  backend.resources.add({ code: "SIM-A-04", isActive: false })
}

describe("centro de mando", () => {
  it("muestra KPIs reales", async () => {
    seed()
    backend.startSessionFor("operator")
    renderApp("/")

    await waitFor(async () => {
      expect(within(await kpi("Incidentes activos")).getByText("3")).toBeInTheDocument()
    })
    expect(within(await kpi("Críticos activos")).getByText("1")).toBeInTheDocument()
    expect(within(await kpi("Recursos disponibles")).getByText("2")).toBeInTheDocument()
    expect(within(await kpi("Recursos en servicio")).getByText("1")).toBeInTheDocument()
    expect(screen.getByText("Datos de las 12:00:00")).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Mapa" })).toBeInTheDocument()
  })

  it("lista solo incidentes activos, por prioridad, y filtra desde la URL", async () => {
    seed()
    backend.startSessionFor("operator")
    const { user, router } = renderApp("/")

    const panel = (await screen.findByRole("heading", { name: "Incidentes activos" })).closest(
      "section"
    )
    if (!panel) throw new Error("panel")
    await within(panel).findByText("Incendio crítico")
    const codes = within(panel)
      .getAllByRole("button", { name: /^Ver INC-/ })
      .map((button) => button.textContent)
    expect(codes).toEqual(["INC-000002", "INC-000001", "INC-000003"])
    expect(within(panel).queryByText("Ya cerrado")).not.toBeInTheDocument()

    await user.selectOptions(within(panel).getByLabelText("Prioridad"), "critical")
    await waitFor(() => {
      expect(within(panel).queryByText("Temporal")).not.toBeInTheDocument()
    })
    expect(router.state.location.search).toBe("?priority=critical")
  })

  it("al seleccionar un incidente muestra su resumen y últimos eventos sin salir", async () => {
    seed()
    backend.startSessionFor("coordinator")
    const { user, router } = renderApp("/")

    expect(
      await screen.findByText("Selecciona un incidente de la lista para ver su resumen.")
    ).toBeInTheDocument()
    await user.click(
      await screen.findByRole("button", { name: "Ver INC-000001 en el panel lateral" })
    )

    expect(await screen.findByRole("heading", { name: "Temporal" })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/")
    expect(router.state.location.search).toBe(
      `?incident=${backend.incidents.byCode("INC-000001").id}`
    )
    expect(await screen.findByText("Incidente registrado con prioridad Alta")).toBeInTheDocument()
    // Las acciones de estado y de recursos están en el propio panel lateral.
    expect(screen.getByRole("button", { name: "Marcar como controlado" })).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Recursos asignados" })).toBeInTheDocument()

    // Ficha completa y vuelta al centro de mando con la misma selección.
    await user.click(screen.getByRole("link", { name: "Abrir ficha completa" }))
    await user.click(await screen.findByRole("link", { name: "Volver" }))
    expect(await screen.findByRole("button", { name: "Cerrar panel" })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/")

    await user.click(screen.getByRole("button", { name: "Cerrar panel" }))
    expect(
      await screen.findByText("Selecciona un incidente de la lista para ver su resumen.")
    ).toBeInTheDocument()
  })

  it("resume los recursos por estado con acceso al listado filtrado", async () => {
    seed()
    backend.startSessionFor("operator")
    const { user, router } = renderApp("/")

    const link = await screen.findByRole("link", { name: "Ver recursos: En servicio" })
    expect(within(link).getByText("1")).toBeInTheDocument()
    expect(screen.getByText("Desactivado")).toBeInTheDocument()

    await user.click(link)
    expect(await screen.findByRole("link", { name: "SIM-A-03" })).toBeInTheDocument()
    expect(router.state.location.search).toBe("?status=in_service")
  })

  it("si el resumen falla, los KPIs lo indican sin inventar cifras", async () => {
    backend.failDashboard = true
    backend.startSessionFor("operator")
    renderApp("/", { retry: false })

    await waitFor(async () => {
      expect(within(await kpi("Incidentes activos")).getByText("No disponible")).toBeInTheDocument()
    })
  })

  it("un cambio de estado de recurso refresca los KPIs", async () => {
    seed()
    const resource = backend.resources.byCode("SIM-A-01")
    backend.startSessionFor("operator")
    const { user, router } = renderApp("/")
    await waitFor(async () => {
      expect(within(await kpi("Recursos en servicio")).getByText("1")).toBeInTheDocument()
    })

    await router.navigate(`/resources/${resource.id}`)
    await user.click(await screen.findByRole("button", { name: "Poner en servicio" }))
    await screen.findByRole("button", { name: "Marcar disponible" })
    await router.navigate("/")

    await waitFor(async () => {
      expect(within(await kpi("Recursos en servicio")).getByText("2")).toBeInTheDocument()
    })
  })
})
