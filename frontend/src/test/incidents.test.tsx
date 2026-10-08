/**
 * Pantallas de incidentes contra el backend falso: listado con filtros en la
 * URL, detalle con historial, cambios de estado, conflicto 409, edición,
 * notas, alta y permisos por rol.
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

function lastListQuery(): URLSearchParams {
  const call = backend.calls.filter((c) => c.path === "/incidents" && c.method === "GET").at(-1)
  if (!call) throw new Error("sin llamadas al listado")
  return call.query
}

describe("listado de incidentes", () => {
  it("muestra los incidentes de la API con prioridad, estado y marca de simulado", async () => {
    backend.incidents.add({
      title: "Incendio de prueba",
      priority: "critical",
      typeCode: "wildfire",
    })
    backend.incidents.add({ title: "Colisión de prueba", priority: "low" })
    backend.startSessionFor("operator")

    renderApp("/incidents")

    expect(await screen.findByText("Incendio de prueba")).toBeInTheDocument()
    const row = rowFor("INC-000001")
    expect(within(row).getByText("Crítica")).toBeInTheDocument()
    expect(within(row).getByText("Recibido")).toBeInTheDocument()
    expect(within(row).getByText("Incendio forestal")).toBeInTheDocument()
    expect(within(row).getByText("Simulado")).toBeInTheDocument()
    // Orden por prioridad que devuelve la API.
    const codes = screen.getAllByRole("link", { name: /^INC-/ }).map((link) => link.textContent)
    expect(codes).toEqual(["INC-000001", "INC-000002"])
    // El operador puede consultar, pero no dar de alta.
    expect(screen.queryByText("Nuevo incidente")).not.toBeInTheDocument()
  })

  it("guarda los filtros en la URL y los envía a la API", async () => {
    backend.incidents.add({ title: "Abierto" })
    backend.incidents.add({ title: "Ya cerrado", status: "closed" })
    backend.startSessionFor("coordinator")
    const { user, router } = renderApp("/incidents")

    await screen.findByText("Abierto")
    expect(screen.queryByText("Ya cerrado")).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText("Estado"), "closed")
    expect(await screen.findByText("Ya cerrado")).toBeInTheDocument()
    expect(router.state.location.search).toBe("?status=closed")
    expect(lastListQuery().getAll("status")).toEqual(["closed"])
    // Un estado elegido explícitamente se busca también entre los finalizados.
    expect(lastListQuery().get("active")).toBe("false")

    await user.click(screen.getByRole("button", { name: "Limpiar filtros" }))
    expect(await screen.findByText("Abierto")).toBeInTheDocument()
    expect(router.state.location.search).toBe("")
  })

  it("busca por texto al enviar y muestra el vacío filtrado", async () => {
    backend.incidents.add({ title: "Inundación de prueba" })
    backend.startSessionFor("operator")
    const { user, router } = renderApp("/incidents")
    await screen.findByText("Inundación de prueba")

    await user.type(screen.getByRole("searchbox"), "no-existe{Enter}")

    expect(
      await screen.findByText("Ningún incidente coincide con los filtros.")
    ).toBeInTheDocument()
    expect(router.state.location.search).toBe("?q=no-existe")
    expect(lastListQuery().get("q")).toBe("no-existe")
  })

  it("restaura los filtros desde la URL", async () => {
    backend.incidents.add({ title: "Incidente urgente", priority: "high" })
    backend.incidents.add({ title: "Incidente leve", priority: "low" })
    backend.startSessionFor("operator")

    renderApp("/incidents?priority=low&sort=-reported_at")

    expect(await screen.findByText("Incidente leve")).toBeInTheDocument()
    expect(screen.queryByText("Incidente urgente")).not.toBeInTheDocument()
    expect(screen.getByLabelText("Prioridad")).toHaveValue("low")
    expect(lastListQuery().get("sort")).toBe("-reported_at")
  })

  it("muestra el estado de error y permite reintentar", async () => {
    backend.incidents.add({ title: "Recuperado" })
    backend.incidents.failList = true
    backend.startSessionFor("operator")
    const { user } = renderApp("/incidents", { retry: false })

    expect(await screen.findByText("No se han podido cargar los datos")).toBeInTheDocument()
    backend.incidents.failList = false
    await user.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(await screen.findByText("Recuperado")).toBeInTheDocument()
  })

  it("todos los roles ven Incidentes en la navegación", async () => {
    backend.startSessionFor("operator")
    renderApp("/")
    const nav = await screen.findByRole("navigation", { name: "Navegación principal" })
    expect(within(nav).getByRole("link", { name: "Incidentes" })).toBeInTheDocument()
  })
})

describe("detalle de incidente", () => {
  it("muestra cabecera, historial con el sistema como actor y sin acciones para operator", async () => {
    const incident = backend.incidents.add({ title: "Temporal de prueba", priority: "high" })
    backend.incidents.add({ title: "Hijo de prueba", parentCode: incident.code })
    backend.startSessionFor("operator")

    renderApp(`/incidents/${incident.id}`)

    expect(await screen.findByRole("heading", { name: "Temporal de prueba" })).toBeInTheDocument()
    expect(screen.getByText("INC-000001")).toBeInTheDocument()
    expect(screen.getAllByText("Simulado").length).toBeGreaterThan(0)
    expect(await screen.findByText("Incidente registrado con prioridad Alta")).toBeInTheDocument()
    expect(screen.getByText("Sistema")).toBeInTheDocument()
    // Relación padre/hijo.
    expect(screen.getByRole("link", { name: "INC-000002" })).toBeInTheDocument()
    // Sin `incidents:update`: ni acciones, ni edición, ni notas.
    expect(screen.queryByRole("button", { name: "Pasar a valoración" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Añadir nota" })).not.toBeInTheDocument()
  })

  it("ofrece solo las transiciones que permite el backend y aplica el cambio", async () => {
    const incident = backend.incidents.add({ title: "Para valorar" })
    backend.startSessionFor("coordinator")
    const { user } = renderApp(`/incidents/${incident.id}`)

    await screen.findByRole("heading", { name: "Para valorar" })
    expect(screen.queryByRole("button", { name: "Iniciar intervención" })).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Pasar a valoración" }))

    expect(await screen.findByText("Estado: Recibido → En valoración")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Iniciar intervención" })).toBeInTheDocument()
    expect(backend.incidents.byCode(incident.code).version).toBe(2)
  })

  it("cerrar pide confirmación, registra el motivo y deja el incidente solo para notas", async () => {
    const incident = backend.incidents.add({ title: "Controlado", status: "controlled" })
    backend.startSessionFor("coordinator")
    const { user } = renderApp(`/incidents/${incident.id}`)
    await screen.findByRole("heading", { name: "Controlado" })

    await user.click(screen.getByRole("button", { name: "Cerrar incidente" }))
    const dialog = await screen.findByRole("alertdialog")
    // Cancelar no cambia nada.
    await user.click(within(dialog).getByRole("button", { name: "No, mantener" }))
    expect(backend.incidents.byCode(incident.code).status).toBe("controlled")

    await user.click(screen.getByRole("button", { name: "Cerrar incidente" }))
    const again = await screen.findByRole("alertdialog")
    await user.type(within(again).getByLabelText("Motivo (opcional)"), "Fin de la intervención")
    await user.click(within(again).getByRole("button", { name: "Cerrar incidente" }))

    expect(
      await screen.findByText(
        "Incidente finalizado: ya no admite cambios de estado ni edición, pero sí notas."
      )
    ).toBeInTheDocument()
    expect(await screen.findByText("Motivo: Fin de la intervención")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Añadir nota" })).toBeInTheDocument()
  })

  it("ante un 409 avisa del cambio ajeno y permite recargar", async () => {
    const incident = backend.incidents.add({ title: "Concurrente" })
    backend.startSessionFor("coordinator")
    const { user } = renderApp(`/incidents/${incident.id}`)
    await screen.findByRole("heading", { name: "Concurrente" })

    backend.incidents.touch(incident.code) // otra persona lo modifica
    await user.click(screen.getByRole("button", { name: "Pasar a valoración" }))

    expect(await screen.findByText("El incidente ha cambiado")).toBeInTheDocument()
    expect(backend.incidents.byCode(incident.code).status).toBe("received")

    await user.click(screen.getByRole("button", { name: "Recargar" }))
    await waitFor(() => {
      expect(screen.queryByText("El incidente ha cambiado")).not.toBeInTheDocument()
    })
    // Con la versión recargada, el mismo cambio ya funciona.
    await user.click(screen.getByRole("button", { name: "Pasar a valoración" }))
    expect(await screen.findByText("Estado: Recibido → En valoración")).toBeInTheDocument()
  })

  it("edita solo lo que cambia y no llama a la API si no hay cambios", async () => {
    const incident = backend.incidents.add({ title: "Título original" })
    backend.startSessionFor("coordinator")
    const { user } = renderApp(`/incidents/${incident.id}`)
    await screen.findByRole("heading", { name: "Título original" })

    await user.click(screen.getByRole("button", { name: "Editar" }))
    await user.click(screen.getByRole("button", { name: "Guardar" }))
    expect(backend.calls.filter((call) => call.method === "PATCH")).toHaveLength(0)

    await user.click(screen.getByRole("button", { name: "Editar" }))
    const title = screen.getByLabelText("Título")
    await user.clear(title)
    await user.type(title, "Título corregido")
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    expect(await screen.findByRole("heading", { name: "Título corregido" })).toBeInTheDocument()
    expect(await screen.findByText("Datos modificados: título")).toBeInTheDocument()
    const patch = backend.calls.find((call) => call.method === "PATCH")
    expect(patch?.body).toEqual({ title: "Título corregido", version: 1 })
  })

  it("añade notas al historial", async () => {
    const incident = backend.incidents.add({ title: "Con notas" })
    backend.startSessionFor("coordinator")
    const { user } = renderApp(`/incidents/${incident.id}`)
    await screen.findByRole("heading", { name: "Con notas" })

    await user.click(screen.getByRole("button", { name: "Añadir nota" }))
    expect(await screen.findByText("Escribe la nota.")).toBeInTheDocument()

    await user.type(screen.getByLabelText("Nota"), "Zona señalizada")
    await user.click(screen.getByRole("button", { name: "Añadir nota" }))

    expect(await screen.findByText("Zona señalizada")).toBeInTheDocument()
    expect(screen.getByLabelText("Nota")).toHaveValue("")
  })

  it("informa si el incidente no existe", async () => {
    backend.startSessionFor("operator")
    renderApp("/incidents/00000000-0000-4000-8000-00000000ffff")

    expect(
      await screen.findByText("El incidente no existe o ya no está disponible.")
    ).toBeInTheDocument()
  })
})

describe("alta de incidente", () => {
  it("valida, muestra los datos del tipo y lleva al detalle del incidente creado", async () => {
    backend.startSessionFor("coordinator")
    const { user, router } = renderApp("/incidents/new")

    await user.click(await screen.findByRole("button", { name: "Registrar incidente" }))
    expect(await screen.findByText("Selecciona el tipo de incidente.")).toBeInTheDocument()
    expect(screen.getByText("Escribe un título.")).toBeInTheDocument()
    expect(
      backend.calls.filter((call) => call.method === "POST" && call.path === "/incidents")
    ).toHaveLength(0)

    await user.selectOptions(screen.getByLabelText("Tipo de incidente"), "Incendio forestal")
    expect(screen.getByRole("option", { name: "Por defecto del tipo (Alta)" })).toBeInTheDocument()
    await user.type(screen.getByLabelText("Título"), "Incendio nuevo")
    await user.type(screen.getByLabelText("Municipio"), "Siero")
    await user.type(screen.getByLabelText("Superficie afectada (ha)"), "3,5")
    await user.selectOptions(screen.getByLabelText("Vegetación"), "Matorral")
    await user.click(screen.getByRole("button", { name: "Registrar incidente" }))

    expect(await screen.findByRole("heading", { name: "Incendio nuevo" })).toBeInTheDocument()
    expect(router.state.location.pathname).toMatch(/^\/incidents\/20000000-/)
    const post = backend.calls.find((call) => call.method === "POST" && call.path === "/incidents")
    expect(post?.body).toMatchObject({
      title: "Incendio nuevo",
      location: { municipality: "Siero", description: null },
      priority: null,
      details: { affected_hectares: "3.5", vegetation: "scrub" },
    })
  })

  it("rechaza valores fuera de rango antes de llamar a la API", async () => {
    backend.startSessionFor("coordinator")
    const { user } = renderApp("/incidents/new")

    await user.type(await screen.findByLabelText("Personas afectadas"), "-3")
    await user.click(screen.getByRole("button", { name: "Registrar incidente" }))

    expect(await screen.findByText("Introduce un valor entre 0 y 100000.")).toBeInTheDocument()
  })

  it("operator no puede abrir el alta", async () => {
    backend.startSessionFor("operator")
    renderApp("/incidents/new")

    expect(await screen.findByText("Acceso no permitido")).toBeInTheDocument()
    expect(backend.calls.filter((call) => call.path === "/incident-types")).toHaveLength(0)
  })
})
