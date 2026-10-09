/**
 * Asignación de recursos (Fase 4) con el backend falso: el sistema informa
 * (candidatos por ETA estimada), la persona decide y confirma; llegada,
 * retirada con motivo, reasignación, cierre con recursos, ficha del recurso y
 * centro de mando (panel lateral, indicador y bases en el mapa).
 */
import { screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import { type FakeBackend, installFakeBackend } from "./fake-backend"
import { renderApp } from "./render-app"

let backend: FakeBackend

beforeEach(() => {
  backend = installFakeBackend()
})

const OVIEDO = { latitude: 43.3614, longitude: -5.8494 }
const GIJON = { latitude: 43.5357, longitude: -5.6615 }
const SIERO = { latitude: 43.392, longitude: -5.662 }

function seed() {
  const incident = backend.incidents.add({
    title: "Incendio en nave",
    typeCode: "wildfire",
    coordinates: OVIEDO,
  })
  backend.resources.add({ code: "SIM-LEJOS", base: GIJON })
  backend.resources.add({ code: "SIM-CERCA", base: SIERO })
  backend.resources.add({ code: "SIM-SVB", typeCode: "ambulance_basic", base: OVIEDO })
  backend.resources.add({ code: "SIM-ROTO", status: "out_of_service", base: OVIEDO })
  return incident
}

async function assignmentsPanel(): Promise<HTMLElement> {
  const heading = await screen.findByRole("heading", { name: "Recursos asignados" })
  const panel = heading.closest("section")
  if (!panel) throw new Error("panel")
  return panel
}

describe("asignación desde la ficha del incidente", () => {
  it("lista candidatos por ETA estimada, sin preselección, y asigna al confirmar", async () => {
    const incident = seed()
    backend.startSessionFor("coordinator")
    const { user } = renderApp(`/incidents/${incident.id}`)

    await user.click(
      await within(await assignmentsPanel()).findByRole("button", { name: "Asignar recurso" })
    )
    const dialog = await screen.findByRole("dialog")
    await within(dialog).findByText("SIM-CERCA")

    const codes = within(dialog)
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).getAllByRole("cell")[0]?.textContent ?? "")
    // Más cerca primero; el fuera de servicio no aparece.
    const order = ["SIM-SVB", "SIM-CERCA", "SIM-LEJOS"]
    expect(codes.map((text) => order.find((code) => text.startsWith(code)))).toEqual(order)
    expect(within(dialog).queryByText("SIM-ROTO")).not.toBeInTheDocument()
    // Tipos sugeridos marcados; la ETA siempre como estimación.
    expect(within(dialog).getAllByText("Sugerido")).toHaveLength(2)
    expect(within(dialog).getAllByText("(estimado)").length).toBe(3)
    // Nada viene elegido: no hay ninguna fila seleccionada ni llamada a la API.
    expect(
      backend.calls.filter((call) => call.method === "POST" && call.path.includes("assignments"))
    ).toHaveLength(0)

    await user.click(within(dialog).getByRole("button", { name: "Asignar SIM-CERCA" }))

    const panel = await assignmentsPanel()
    expect(await within(panel).findByText("SIM-CERCA")).toBeInTheDocument()
    expect(within(panel).getByText("Asignado, en camino")).toBeInTheDocument()
    expect(within(panel).getByText("(estimado)")).toBeInTheDocument()
    expect(await screen.findByText("Recurso asignado: SIM-CERCA")).toBeInTheDocument()
    expect(screen.getByText("Automático por la asignación de recursos")).toBeInTheDocument()
    const post = backend.calls.find(
      (call) => call.method === "POST" && call.path.endsWith("/assignments")
    )
    expect(post?.body).toEqual({
      resource_id: backend.resources.byCode("SIM-CERCA").id,
      version: 1,
      reassign: false,
    })
  })

  it("retirar exige motivo y, si era el último, el incidente vuelve a valoración", async () => {
    const incident = seed()
    backend.assignments.assign(incident.code, "SIM-CERCA")
    backend.startSessionFor("coordinator")
    const { user } = renderApp(`/incidents/${incident.id}`)

    await user.click(
      await within(await assignmentsPanel()).findByRole("button", { name: "Retirar SIM-CERCA" })
    )
    const dialog = await screen.findByRole("alertdialog")
    const confirm = within(dialog).getByRole("button", { name: "Retirar" })
    expect(confirm).toBeDisabled()
    await user.selectOptions(within(dialog).getByLabelText("Motivo (obligatorio)"), "completed")
    await user.click(confirm)

    expect(await screen.findByText("Recurso retirado: SIM-CERCA")).toBeInTheDocument()
    expect(screen.getAllByText("Misión cumplida").length).toBeGreaterThan(0)
    expect(backend.resources.byCode("SIM-CERCA").status).toBe("available")
    expect(backend.incidents.byCode(incident.code).status).toBe("assessing")
  })

  it("el operador marca la llegada pero no asigna ni retira", async () => {
    const incident = seed()
    backend.assignments.assign(incident.code, "SIM-CERCA")
    backend.startSessionFor("operator")
    const { user } = renderApp(`/incidents/${incident.id}`)

    const panel = await assignmentsPanel()
    expect(within(panel).queryByRole("button", { name: "Asignar recurso" })).not.toBeInTheDocument()
    expect(within(panel).queryByRole("button", { name: /^Retirar/ })).not.toBeInTheDocument()
    await user.click(
      await within(panel).findByRole("button", { name: "Marcar SIM-CERCA en el lugar" })
    )

    expect(await within(panel).findByText("En el lugar")).toBeInTheDocument()
    expect(await screen.findByText("SIM-CERCA en el lugar")).toBeInTheDocument()
    // Llegar no cambia el estado del incidente.
    expect(backend.incidents.byCode(incident.code).status).toBe("resources_assigned")
  })

  it("reasignar un recurso de otro incidente pide confirmación", async () => {
    const incident = seed()
    const other = backend.incidents.add({ title: "Otro", coordinates: GIJON })
    backend.assignments.assign(other.code, "SIM-CERCA")
    backend.startSessionFor("coordinator")
    const { user } = renderApp(`/incidents/${incident.id}`)

    await user.click(
      await within(await assignmentsPanel()).findByRole("button", { name: "Asignar recurso" })
    )
    const dialog = await screen.findByRole("dialog")
    await within(dialog).findByText("SIM-LEJOS")
    expect(within(dialog).queryByText("SIM-CERCA")).not.toBeInTheDocument()
    await user.click(
      within(dialog).getByRole("checkbox", {
        name: "Incluir recursos asignados a otros incidentes",
      })
    )
    await user.click(
      await within(dialog).findByRole("button", {
        name: `Reasignar SIM-CERCA desde ${other.code}`,
      })
    )
    const confirm = await screen.findByRole("alertdialog")
    expect(
      within(confirm).getByText(`¿Reasignar SIM-CERCA de ${other.code} a ${incident.code}?`)
    ).toBeInTheDocument()
    await user.click(within(confirm).getByRole("button", { name: "Reasignar" }))

    expect(
      await screen.findByText(new RegExp(`Reasignado desde ${other.code}`))
    ).toBeInTheDocument()
    const post = backend.calls.find(
      (call) => call.method === "POST" && call.path.endsWith("/assignments")
    )
    expect(post?.body).toMatchObject({ reassign: true })
    expect(backend.incidents.byCode(other.code).status).toBe("assessing")
  })

  it("cerrar o cancelar enumera los recursos que se retirarán", async () => {
    const incident = seed()
    backend.assignments.assign(incident.code, "SIM-CERCA")
    backend.assignments.assign(incident.code, "SIM-LEJOS")
    backend.startSessionFor("coordinator")
    const { user } = renderApp(`/incidents/${incident.id}`)

    await user.click(await screen.findByRole("button", { name: "Cancelar incidente" }))
    const dialog = await screen.findByRole("alertdialog")
    expect(within(dialog).getByText("Se retirarán los 2 recursos asignados:")).toBeInTheDocument()
    expect(await within(dialog).findByText("SIM-CERCA")).toBeInTheDocument()
    expect(within(dialog).getByText("SIM-LEJOS")).toBeInTheDocument()
    await user.click(within(dialog).getByRole("button", { name: "Cancelar incidente" }))

    await waitFor(() => {
      expect(backend.resources.byCode("SIM-CERCA").status).toBe("available")
    })
    expect(backend.resources.byCode("SIM-LEJOS").status).toBe("available")
  })
})

describe("recurso asignado", () => {
  it("la ficha muestra la asignación y bloquea su estado y la desactivación", async () => {
    const incident = seed()
    backend.assignments.assign(incident.code, "SIM-CERCA")
    const resource = backend.resources.byCode("SIM-CERCA")
    backend.startSessionFor("admin")
    renderApp(`/resources/${resource.id}`)

    expect(await screen.findByRole("link", { name: incident.code })).toBeInTheDocument()
    expect(
      screen.getByText(
        "Mientras esté asignado, su estado lo gobierna la asignación: se retira desde el incidente."
      )
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Marcar disponible" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Desactivar" })).toBeDisabled()
    expect(screen.getByText("(estimado)")).toBeInTheDocument()
  })
})

describe("centro de mando con asignaciones", () => {
  it("panel lateral, indicador en la lista y bases de los asignados en el mapa", async () => {
    const incident = seed()
    backend.assignments.assign(incident.code, "SIM-CERCA")
    backend.startSessionFor("operator")
    renderApp(`/?incident=${incident.id}`)

    // Panel lateral: los mismos recursos asignados y acciones que la ficha completa.
    const panel = await assignmentsPanel()
    expect(await within(panel).findByRole("link", { name: "SIM-CERCA" })).toBeInTheDocument()
    expect(
      within(panel).getByRole("button", { name: "Marcar SIM-CERCA en el lugar" })
    ).toBeInTheDocument()
    // El operador marca la llegada, pero no asigna ni retira.
    expect(within(panel).queryByRole("button", { name: "Asignar recurso" })).not.toBeInTheDocument()
    expect(screen.getAllByText("1 recurso asignado").length).toBeGreaterThan(0)
    const map = await screen.findByRole("region", { name: "Mapa de incidentes activos" })
    expect(
      await within(map).findByRole("img", {
        name: /^Base de recursos asignados: SIM-CERCA, Autobomba, ETA ≈/,
      })
    ).toBeInTheDocument()
    // Solo las bases de los recursos asignados al incidente seleccionado.
    expect(within(map).queryByRole("img", { name: /SIM-LEJOS/ })).not.toBeInTheDocument()
  })

  it("los recursos que comparten base se muestran en un solo marcador", async () => {
    const incident = seed()
    backend.resources.add({ code: "SIM-CERCA-2", base: SIERO })
    backend.assignments.assign(incident.code, "SIM-CERCA")
    backend.assignments.assign(incident.code, "SIM-CERCA-2")
    backend.startSessionFor("operator")
    renderApp(`/?incident=${incident.id}`)

    const map = await screen.findByRole("region", { name: "Mapa de incidentes activos" })
    const marker = await within(map).findByRole("img", { name: /SIM-CERCA,.*SIM-CERCA-2,/ })
    expect(marker).toHaveTextContent("SIM-CERCA+1")
    expect(within(map).getAllByRole("img", { name: /^Base de recursos/ })).toHaveLength(1)
  })

  it("si PostgreSQL aborta la operación por concurrencia, avisa sin guardar nada", async () => {
    const incident = seed()
    backend.assignments.abortNextWrite = true
    backend.startSessionFor("coordinator")
    const { user } = renderApp(`/incidents/${incident.id}`)

    await user.click(
      await within(await assignmentsPanel()).findByRole("button", { name: "Asignar recurso" })
    )
    const dialog = await screen.findByRole("dialog")
    await user.click(await within(dialog).findByRole("button", { name: "Asignar SIM-CERCA" }))

    expect(
      await within(dialog).findByText(
        "Otra operación simultánea ha impedido guardar el cambio. No se ha guardado nada: recarga y vuelve a intentarlo."
      )
    ).toBeInTheDocument()
    expect(backend.assignments.assignments).toHaveLength(0)
  })
})
