import { beforeEach, describe, expect, it, vi } from "vitest"

import { installFakeBackend, type FakeBackend } from "@/test/fake-backend"

import {
  ApiError,
  apiRequest,
  getAccessToken,
  onSessionExpired,
  refreshAccessToken,
  setAccessToken,
} from "./api-client"

let backend: FakeBackend

beforeEach(() => {
  backend = installFakeBackend()
})

async function loginAs(role: "admin" | "coordinator" | "operator") {
  backend.startSessionFor(role)
  expect(await refreshAccessToken()).toBe(true)
}

describe("apiRequest", () => {
  it("envía el access token en memoria como Bearer", async () => {
    await loginAs("coordinator")

    await apiRequest("/auth/me")

    const call = backend.callsTo("/auth/me")[0]
    expect(call?.authorization).toBe(`Bearer ${String(getAccessToken())}`)
  })

  it("ante un 401 hace refresh y reintenta una vez", async () => {
    await loginAs("coordinator")
    backend.expireAccessTokens()

    const me = await apiRequest<{ role: string }>("/auth/me")

    expect(me.role).toBe("coordinator")
    expect(backend.callsTo("/auth/refresh")).toHaveLength(2) // login simulado + refresh
    expect(backend.callsTo("/auth/me")).toHaveLength(2) // intento + reintento
  })

  it("comparte un único refresh entre peticiones simultáneas", async () => {
    await loginAs("coordinator")
    backend.expireAccessTokens()
    const refreshesBefore = backend.callsTo("/auth/refresh").length

    await Promise.all([
      apiRequest("/auth/me"),
      apiRequest("/organizations"),
      apiRequest("/auth/me"),
    ])

    expect(backend.callsTo("/auth/refresh").length - refreshesBefore).toBe(1)
  })

  it("reintenta el refresh una sola vez ante refresh_token_rotated", async () => {
    await loginAs("coordinator")
    backend.expireAccessTokens()
    backend.rotateRaceOnNextRefresh = true
    const refreshesBefore = backend.callsTo("/auth/refresh").length

    await apiRequest("/auth/me")

    expect(backend.callsTo("/auth/refresh").length - refreshesBefore).toBe(2)
  })

  it("si el refresh falla: borra el token, avisa de sesión expirada y no entra en bucle", async () => {
    await loginAs("coordinator")
    backend.expireAccessTokens()
    backend.revokeAllSessions()
    const expired = vi.fn()
    const unsubscribe = onSessionExpired(expired)
    const callsBefore = backend.calls.length

    await expect(apiRequest("/auth/me")).rejects.toMatchObject({ status: 401 })

    expect(getAccessToken()).toBeNull()
    expect(expired).toHaveBeenCalledOnce()
    // Petición original + un refresh: nada más.
    expect(backend.calls.length - callsBefore).toBe(2)
    unsubscribe()
  })

  it("no intenta refresh en endpoints públicos (401 de login = credenciales)", async () => {
    const error = await apiRequest("/auth/login", {
      method: "POST",
      body: { email: "nadie@example.test", password: "x" },
      auth: false,
    }).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe("invalid_credentials")
    expect(backend.callsTo("/auth/refresh")).toHaveLength(0)
  })

  it("un fallo transitorio del refresh (5xx) no cierra la sesión", async () => {
    setAccessToken("access-caducado")
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) => {
        await Promise.resolve()
        return input.endsWith("/auth/refresh")
          ? new Response(JSON.stringify({ detail: "internal_error" }), { status: 500 })
          : new Response(JSON.stringify({ detail: "invalid_token" }), { status: 401 })
      })
    )
    const expired = vi.fn()
    const unsubscribe = onSessionExpired(expired)

    await expect(apiRequest("/auth/me")).rejects.toMatchObject({ status: 500 })

    expect(expired).not.toHaveBeenCalled()
    expect(getAccessToken()).toBe("access-caducado")
    unsubscribe()
  })

  it("traduce un fallo de red en ApiError con status 0", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")))

    const error = await apiRequest("/health", { auth: false }).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).isNetworkError).toBe(true)
  })
})
