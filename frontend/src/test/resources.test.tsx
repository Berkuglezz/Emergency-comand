/**
 * Pantallas de recursos contra el backend falso: listado con filtros en la URL,
 * ficha, cambio de estado, conflicto 409, desactivación, edición, alta y
 * permisos por rol.
 */
import { screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import { type FakeBackend, installFakeBackend } from "./fake-backend"
import { renderApp } from "./render-app"

let backend: FakeBackend

beforeEach(() => {
  backend = installFakeBackend()
})

function rowFor(code: string): HTMLElement {
  const row = screen.getByRole("link", { name: code }).closest("tr")
  if (!row) throw new Error(code)
  return row
}

const writes = () =>
  backend.calls.filter((call) => call.method !== "GET" && call.path.startsWith("/resources"))

describe("listado de recursos", () => {
  it("muestra los recursos con estado, tipo y marca de simulado; operator no da de alta", async () => {
    backend.resources.add({ code: "SIM-A-01", name: "Autobomba 1 (simulado)" })
    backend.resources.add({ code: "SIM-B-01", status: "in_service", typeCode: "ambulance_basic" })
    backend.startSessionFor("operator")

    renderApp("/resources")

    expect(await screen.findByText("Autobomba 1 (simulado)")).toBeInTheDocument()
    const row = rowFor("SIM-B-01")
    expect(within(row).getByText("En servicio")).toBeInTheDocument()
    expect(within(row).getByText("Ambulancia de soporte vital básico")).toBeInTheDocument()
    expect(within(row).getByText("Simulado")).toBeInTheDocument()
    expect(screen.queryByText("Nuevo recurso")).not.toBeInTheDocument()
    // Sin `organizations:read` no se ofrece el filtro ni se pide la lista (403 seguro).
    expect(screen.queryByLabelText("Organización")).not.toBeInTheDocument()
    expect(backend.callsTo("/organizations")).toHaveLength(0)
  })

  it("filtra por estado desde la URL y muestra los desactivados solo si se piden", async () => {
    backend.resources.add({ code: "SIM-A-01" })
    backend.resources.add({ code: "SIM-A-02", status: "out_of_service" })
    backend.resources.add({ code: "SIM-A-03", isActive: false })
    backend.startSessionFor("coordinator")
    const { user, router } = renderApp("/resources")

    await screen.findByRole("link", { name: "SIM-A-01" })
    expect(screen.queryByRole("link", { name: "SIM-A-03" })).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText("Estado"), "out_of_service")
    await waitFor(() => {
      expect(screen.queryByRole("link", { name: "SIM-A-01" })).not.toBeInTheDocument()
    })
    expect(screen.getByRole("link", { name: "SIM-A-02" })).toBeInTheDocument()
    expect(router.state.location.search).toBe("?status=out_of_service")

    await user.click(screen.getByRole("button", { name: "Limpiar filtros" }))
    await user.click(screen.getByLabelText("Incluir desactivados"))
    const inactive = await screen.findByRole("link", { name: "SIM-A-03" })
    expect(
      within(inactive.closest("tr") ?? document.body).getByText("Desactivado")
    ).toBeInTheDocument()
  })

  it("«Volver» desde la ficha conserva los filtros del listado", async () => {
    backend.resources.add({ code: "SIM-A-01" })
    backend.startSessionFor("operator")
    const { user, router } = renderApp("/resources?status=available&sort=status")

    await user.click(await screen.findByRole("link", { name: "SIM-A-01" }))
    await screen.findByRole("heading", { name: "SIM-A-01 (simulado)" })
    await user.click(screen.getByRole("link", { name: "Volver" }))

    await screen.findByRole("link", { name: "SIM-A-01" })
    expect(router.state.location.pathname).toBe("/resources")
    expect(router.state.location.search).toBe("?status=available&sort=status")
  })
})

describe("ficha de recurso", () => {
  it("cualquier rol cambia el estado operativo, pero solo admin edita la ficha", async () => {
    const resource = backend.resources.add({ code: "SIM-A-01" })
    backend.startSessionFor("operator")
    const { user } = renderApp(`/resources/${resource.id}`)

    await screen.findByRole("heading", { name: "SIM-A-01 (simulado)" })
    // Se ofrecen los otros dos estados, nunca el actual.
    expect(screen.queryByRole("button", { name: "Marcar disponible" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Desactivar" })).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Poner en servicio" }))

    expect(await screen.findByRole("button", { name: "Marcar disponible" })).toBeInTheDocument()
    expect(backend.resources.byCode("SIM-A-01")).toMatchObject({ status: "in_service", version: 2 })
    expect(
      screen.getByText(
        "En esta fase no se guarda el historial del recurso: solo su último cambio de estado."
      )
    ).toBeInTheDocument()
  })

  it("ante un 409 avisa del cambio ajeno y permite recargar", async () => {
    const resource = backend.resources.add({ code: "SIM-A-01" })
    backend.startSessionFor("coordinator")
    const { user } = renderApp(`/resources/${resource.id}`)
    await screen.findByRole("heading", { name: "SIM-A-01 (simulado)" })

    backend.resources.byCode("SIM-A-01").version += 1 // otra persona lo cambia
    await user.click(screen.getByRole("button", { name: "Poner en servicio" }))

    expect(await screen.findByText("El recurso ha cambiado")).toBeInTheDocument()
    expect(backend.resources.byCode("SIM-A-01").status).toBe("available")
    await user.click(screen.getByRole("button", { name: "Recargar" }))
    await waitFor(() => {
      expect(screen.queryByText("El recurso ha cambiado")).not.toBeInTheDocument()
    })
    await user.click(screen.getByRole("button", { name: "Poner en servicio" }))
    expect(await screen.findByRole("button", { name: "Marcar disponible" })).toBeInTheDocument()
  })

  it("desactivar pide confirmación y bloquea los cambios de estado; reactivar no", async () => {
    const resource = backend.resources.add({ code: "SIM-A-01" })
    backend.startSessionFor("admin")
    const { user } = renderApp(`/resources/${resource.id}`)
    await screen.findByRole("heading", { name: "SIM-A-01 (simulado)" })

    await user.click(screen.getByRole("button", { name: "Desactivar" }))
    const dialog = await screen.findByRole("alertdialog")
    await user.click(within(dialog).getByRole("button", { name: "Desactivar" }))

    expect(
      await screen.findByText("Recurso desactivado: no cambia de estado hasta que se reactive.")
    ).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Poner en servicio" })).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Reactivar" }))
    expect(await screen.findByRole("button", { name: "Poner en servicio" })).toBeInTheDocument()
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
    expect(backend.resources.byCode("SIM-A-01")).toMatchObject({ is_active: true, version: 3 })
  })

  it("admin edita solo lo que cambia y no llama a la API sin cambios", async () => {
    const resource = backend.resources.add({ code: "SIM-A-01" })
    backend.startSessionFor("admin")
    const { user } = renderApp(`/resources/${resource.id}`)
    await screen.findByRole("heading", { name: "SIM-A-01 (simulado)" })

    await user.click(screen.getByRole("button", { name: "Editar" }))
    await user.click(await screen.findByRole("button", { name: "Guardar" }))
    expect(writes()).toHaveLength(0)

    await user.click(screen.getByRole("button", { name: "Editar" }))
    const name = await screen.findByLabelText("Nombre")
    await user.clear(name)
    await user.type(name, "Autobomba renombrada")
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    expect(await screen.findByRole("heading", { name: "Autobomba renombrada" })).toBeInTheDocument()
    expect(writes().at(-1)?.body).toEqual({ name: "Autobomba renombrada", version: 1 })
  })

  it("informa si el recurso no existe", async () => {
    backend.startSessionFor("operator")
    renderApp("/resources/00000000-0000-4000-8000-00000000ffff")
    expect(
      await screen.findByText("El recurso no existe o ya no está disponible.")
    ).toBeInTheDocument()
  })
})

describe("alta de recurso", () => {
  it("valida el código, normaliza a mayúsculas y lleva a la ficha creada", async () => {
    backend.startSessionFor("admin")
    const { user, router } = renderApp("/resources/new")

    await user.type(await screen.findByLabelText("Código"), "x")
    await user.click(screen.getByRole("button", { name: "Registrar recurso" }))
    expect(
      await screen.findByText(
        "Usa de 2 a 32 letras, números o guiones, empezando por letra o número."
      )
    ).toBeInTheDocument()
    expect(writes()).toHaveLength(0)

    await user.clear(screen.getByLabelText("Código"))
    await user.type(screen.getByLabelText("Código"), "bom-ovi-09")
    await user.type(screen.getByLabelText("Nombre"), "Autobomba nueva")
    await user.selectOptions(screen.getByLabelText("Tipo de recurso"), "Autobomba")
    await user.selectOptions(
      screen.getByLabelText("Organización"),
      "Organización de prueba (simulado)"
    )
    await user.type(screen.getByLabelText("Municipio base"), "Avilés")
    await user.click(screen.getByRole("button", { name: "Registrar recurso" }))

    expect(await screen.findByRole("heading", { name: "Autobomba nueva" })).toBeInTheDocument()
    expect(screen.getByText("BOM-OVI-09")).toBeInTheDocument()
    expect(router.state.location.pathname).toMatch(/^\/resources\/50000000-/)
    expect(writes()[0]?.body).toMatchObject({ code: "BOM-OVI-09", status: null })
  })

  it("muestra el error de código duplicado que devuelve la API", async () => {
    backend.resources.add({ code: "BOM-01" })
    backend.startSessionFor("admin")
    const { user } = renderApp("/resources/new")

    await user.type(await screen.findByLabelText("Código"), "bom-01")
    await user.type(screen.getByLabelText("Nombre"), "Duplicado")
    await user.selectOptions(screen.getByLabelText("Tipo de recurso"), "Autobomba")
    await user.selectOptions(
      screen.getByLabelText("Organización"),
      "Organización de prueba (simulado)"
    )
    await user.type(screen.getByLabelText("Municipio base"), "Oviedo")
    await user.click(screen.getByRole("button", { name: "Registrar recurso" }))

    expect(await screen.findByText("Ya existe un recurso con ese código.")).toBeInTheDocument()
  })

  it("coordinator no puede abrir el alta", async () => {
    backend.startSessionFor("coordinator")
    renderApp("/resources/new")
    expect(await screen.findByText("Acceso no permitido")).toBeInTheDocument()
  })
})
