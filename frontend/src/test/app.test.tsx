/**
 * Flujos completos de la aplicación contra el backend falso: login, rutas
 * protegidas, navegación por rol, refresh y logout.
 */
import { screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { getAccessToken } from "@/lib/api-client"

import { installFakeBackend, TEST_PASSWORD, type FakeBackend } from "./fake-backend"
import { renderApp } from "./render-app"

let backend: FakeBackend

beforeEach(() => {
  backend = installFakeBackend()
})

async function logIn(
  user: ReturnType<typeof renderApp>["user"],
  email: string,
  password = TEST_PASSWORD
) {
  await user.type(await screen.findByLabelText("Correo electrónico"), email)
  await user.type(screen.getByLabelText("Contraseña"), password)
  await user.click(screen.getByRole("button", { name: "Iniciar sesión" }))
}

function navigation() {
  return screen.getByRole("navigation", { name: "Navegación principal" })
}

describe("rutas protegidas", () => {
  it("sin sesión, cualquier ruta protegida lleva al login", async () => {
    const { router } = renderApp("/organizations")

    expect(await screen.findByRole("button", { name: "Iniciar sesión" })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/login")
    // Se intentó restaurar la sesión con la cookie antes de redirigir.
    expect(backend.callsTo("/auth/refresh")).toHaveLength(1)
  })

  it("restaura la sesión al recargar si la cookie de refresh es válida", async () => {
    backend.startSessionFor("operator")

    renderApp("/")

    expect(await screen.findByRole("heading", { name: "Mapa" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Iniciar sesión" })).not.toBeInTheDocument()
  })

  it("tras el login vuelve a la ruta que se pidió", async () => {
    const { user, router } = renderApp("/organizations")

    await logIn(user, "coordinator@example.test")

    expect(await screen.findByRole("heading", { name: "Organizaciones" })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/organizations")
  })
})

describe("login", () => {
  it("valida el formulario antes de llamar a la API", async () => {
    const { user } = renderApp("/login")

    await user.click(await screen.findByRole("button", { name: "Iniciar sesión" }))

    expect(await screen.findByText("Introduce tu correo electrónico.")).toBeInTheDocument()
    expect(screen.getByText("Introduce tu contraseña.")).toBeInTheDocument()
    expect(screen.getByLabelText("Correo electrónico")).toHaveAttribute("aria-invalid", "true")
    expect(backend.callsTo("/auth/login")).toHaveLength(0)
  })

  it("muestra un error genérico con credenciales incorrectas y vacía la contraseña", async () => {
    const { user } = renderApp("/login")

    await logIn(user, "operator@example.test", "contraseña-incorrecta")

    expect(await screen.findByText("Correo o contraseña incorrectos.")).toBeInTheDocument()
    expect(screen.getByLabelText("Contraseña")).toHaveValue("")
    expect(getAccessToken()).toBeNull()
  })

  it("no guarda tokens en localStorage/sessionStorage ni los escribe en consola", async () => {
    const consoleSpies = (["log", "info", "warn", "error", "debug"] as const).map((method) =>
      vi.spyOn(console, method)
    )
    const { user } = renderApp("/login")

    await logIn(user, "coordinator@example.test")
    await screen.findByRole("heading", { name: "Mapa" })

    expect(getAccessToken()).toMatch(/^access-/)
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    const logged = consoleSpies.flatMap((spy) => spy.mock.calls.flat().map(String)).join("\n")
    expect(logged).not.toMatch(/access-|refresh-|Bearer|password/i)
  })
})

describe("navegación por rol", () => {
  it("operator no ve Organizaciones y la ruta directa muestra acceso no permitido", async () => {
    const { user, router } = renderApp("/login")

    await logIn(user, "operator@example.test")
    await screen.findByRole("heading", { name: "Mapa" })

    const nav = navigation()
    expect(within(nav).getByRole("link", { name: "Centro de mando" })).toBeInTheDocument()
    expect(within(nav).queryByRole("link", { name: "Organizaciones" })).not.toBeInTheDocument()

    await router.navigate("/organizations")
    expect(await screen.findByText("Acceso no permitido")).toBeInTheDocument()
    // El frontend ni siquiera pide los datos; el backend respondería 403 igualmente.
    expect(backend.callsTo("/organizations")).toHaveLength(0)
  })

  it("la navegación se pliega a iconos sin perder los nombres accesibles", async () => {
    const { user } = renderApp("/login")

    await logIn(user, "coordinator@example.test")
    await screen.findByRole("heading", { name: "Mapa" })
    await user.click(screen.getByRole("button", { name: "Plegar la navegación" }))

    const expand = screen.getByRole("button", { name: "Desplegar la navegación" })
    expect(expand).toHaveAttribute("aria-expanded", "false")
    expect(within(navigation()).getByRole("link", { name: "Organizaciones" })).toHaveAttribute(
      "title",
      "Organizaciones"
    )
    expect(screen.getByRole("button", { name: "Cerrar sesión" })).toBeInTheDocument()
    expect(localStorage.getItem("ec.layout.sidebar")).toBe("0")
  })

  it("coordinator ve Organizaciones y carga los datos del backend", async () => {
    const { user } = renderApp("/login")

    await logIn(user, "coordinator@example.test")
    await screen.findByRole("heading", { name: "Mapa" })
    await user.click(within(navigation()).getByRole("link", { name: "Organizaciones" }))

    expect(await screen.findByText("Organización de prueba (simulado)")).toBeInTheDocument()
    expect(screen.getByText("Simulada")).toBeInTheDocument()
  })

  it("muestra el estado vacío de Organizaciones", async () => {
    backend.organizations = []
    backend.startSessionFor("admin")
    renderApp("/organizations")

    expect(await screen.findByText("No hay organizaciones registradas.")).toBeInTheDocument()
  })

  it("muestra el estado de error de Organizaciones y permite reintentar", async () => {
    backend.failOrganizations = true
    backend.startSessionFor("admin")
    const { user } = renderApp("/organizations", { retry: false })

    expect(await screen.findByText("No se han podido cargar los datos")).toBeInTheDocument()

    backend.failOrganizations = false
    await user.click(screen.getByRole("button", { name: "Reintentar" }))
    expect(await screen.findByText("Organización de prueba (simulado)")).toBeInTheDocument()
  })

  it("muestra el estado de carga mientras llegan los datos", async () => {
    backend.startSessionFor("admin")
    renderApp("/organizations")

    // Primero se comprueba la sesión y después el panel indica que está cargando.
    expect(await screen.findByText("Comprobando la sesión…")).toBeInTheDocument()
    const loading = await screen.findByText("Cargando…")
    expect(loading.closest("section")).toHaveAttribute("aria-busy", "true")
    expect(await screen.findByText("Organización de prueba (simulado)")).toBeInTheDocument()
  })
})

describe("sesión", () => {
  it("renueva el access token caducado de forma transparente", async () => {
    const { user } = renderApp("/login")
    await logIn(user, "coordinator@example.test")
    await screen.findByRole("heading", { name: "Mapa" })
    const tokenBefore = getAccessToken()

    backend.expireAccessTokens()
    await user.click(within(navigation()).getByRole("link", { name: "Organizaciones" }))

    expect(await screen.findByText("Organización de prueba (simulado)")).toBeInTheDocument()
    expect(getAccessToken()).not.toBe(tokenBefore)
  })

  it("si el refresh falla definitivamente vuelve al login y borra el token", async () => {
    const { user, router } = renderApp("/login")
    await logIn(user, "coordinator@example.test")
    await screen.findByRole("heading", { name: "Mapa" })

    backend.expireAccessTokens()
    backend.revokeAllSessions()
    await user.click(within(navigation()).getByRole("link", { name: "Organizaciones" }))

    expect(await screen.findByRole("button", { name: "Iniciar sesión" })).toBeInTheDocument()
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/login")
    })
    expect(getAccessToken()).toBeNull()
  })

  it("logout invalida la sesión en el backend y vuelve al login", async () => {
    const { user } = renderApp("/login")
    await logIn(user, "operator@example.test")
    await screen.findByRole("heading", { name: "Mapa" })

    await user.click(screen.getByRole("button", { name: "Cerrar sesión" }))

    expect(await screen.findByRole("button", { name: "Iniciar sesión" })).toBeInTheDocument()
    expect(getAccessToken()).toBeNull()
    expect(backend.cookie).toBeNull()
    expect(backend.callsTo("/auth/logout")).toHaveLength(1)
  })

  it("tras el logout, el siguiente login empieza en el centro de mando", async () => {
    const { user, router } = renderApp("/login")
    await logIn(user, "coordinator@example.test")
    await screen.findByRole("heading", { name: "Mapa" })
    await user.click(within(navigation()).getByRole("link", { name: "Organizaciones" }))
    await screen.findByText("Organización de prueba (simulado)")

    await user.click(screen.getByRole("button", { name: "Cerrar sesión" }))
    await logIn(user, "admin@example.test")

    expect(await screen.findByRole("heading", { name: "Mapa" })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe("/")
  })
})
