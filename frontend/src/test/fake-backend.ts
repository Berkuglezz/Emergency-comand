/**
 * Backend falso en memoria para los tests. Sustituye a `fetch` e imita el
 * contrato real de la API (códigos de error, cookie de refresh con rotación,
 * 401/403). Las credenciales son ficticias y solo existen aquí.
 */
import { vi } from "vitest"

import type { components } from "@/types/api"

import { FakeAssignments } from "./fake-assignments"
import { FakeIncidents } from "./fake-incidents"
import { FakeResources } from "./fake-resources"

type Schemas = components["schemas"]
type Me = Schemas["MeResponse"]

const ORGANIZATION = {
  id: "00000000-0000-4000-8000-000000000001",
  code: "sim-test",
  name: "Organización de prueba (simulado)",
  is_simulated: true,
  is_active: true,
} satisfies Schemas["OrganizationResponse"]

// Mismo mapa que el backend (app/core/permissions.py).
const PERMISSIONS: Record<Me["role"], Me["permissions"]> = {
  admin: [
    "incidents:read",
    "incidents:create",
    "incidents:update",
    "incidents:close",
    "resources:read",
    "resources:update_status",
    "resources:manage",
    "organizations:read",
    "assignments:manage",
    "assignments:update",
  ],
  coordinator: [
    "incidents:read",
    "incidents:create",
    "incidents:update",
    "incidents:close",
    "resources:read",
    "resources:update_status",
    "organizations:read",
    "assignments:manage",
    "assignments:update",
  ],
  operator: ["incidents:read", "resources:read", "resources:update_status", "assignments:update"],
}

export const TEST_PASSWORD = "test-password-123"

function makeUser(role: Me["role"]): Me {
  return {
    id: `00000000-0000-4000-8000-00000000010${String(["admin", "coordinator", "operator"].indexOf(role))}`,
    email: `${role}@example.test`,
    full_name: `Usuario ${role}`,
    role,
    permissions: PERMISSIONS[role],
    organization: ORGANIZATION,
  }
}

export interface RecordedCall {
  method: string
  path: string
  authorization: string | null
  query: URLSearchParams
  /** Cuerpo JSON ya interpretado (sin credenciales: solo se registra fuera del login). */
  body: unknown
}

export class FakeBackend {
  readonly users: Me[] = [makeUser("admin"), makeUser("coordinator"), makeUser("operator")]
  /** Cookie de refresh del «navegador». JavaScript de la app nunca la ve. */
  cookie: string | null = null
  readonly calls: RecordedCall[] = []
  /** Próximo refresh responde `refresh_token_rotated` (carrera entre pestañas). */
  rotateRaceOnNextRefresh = false
  organizations: Schemas["OrganizationResponse"][] = [ORGANIZATION]
  /** El listado de organizaciones responde 500 (error del servidor). */
  failOrganizations = false
  readonly incidents = new FakeIncidents()
  readonly resources = new FakeResources(ORGANIZATION)
  readonly assignments = new FakeAssignments(this.incidents, this.resources)
  /** El resumen del dashboard responde 500. */
  failDashboard = false

  private readonly accessTokens = new Map<string, Me>()
  private readonly refreshTokens = new Map<string, Me>()
  private counter = 0

  readonly fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : String(input), "http://test")
    const method = init?.method ?? "GET"
    const headers = new Headers(init?.headers)
    const authorization = headers.get("Authorization")
    const path = url.pathname.replace(/^\/api\/v1/, "")
    const body =
      typeof init?.body === "string" && path !== "/auth/login"
        ? (JSON.parse(init.body) as unknown)
        : undefined
    this.calls.push({ method, path, authorization, query: url.searchParams, body })
    await Promise.resolve()
    return this.handle(method, path, url.searchParams, authorization, init?.body)
  })

  /** Simula una sesión previa: hay cookie de refresh válida en el navegador. */
  startSessionFor(role: Me["role"]): void {
    this.cookie = this.issueRefresh(this.userFor(role))
  }

  /** Simula la caducidad de todos los access tokens emitidos. */
  expireAccessTokens(): void {
    this.accessTokens.clear()
  }

  /** Simula la revocación de todas las sesiones (refresh tokens). */
  revokeAllSessions(): void {
    this.refreshTokens.clear()
  }

  callsTo(path: string): RecordedCall[] {
    return this.calls.filter((call) => call.path === path)
  }

  userFor(role: Me["role"]): Me {
    const user = this.users.find((candidate) => candidate.role === role)
    if (!user) throw new Error(role)
    return user
  }

  private issueRefresh(user: Me): string {
    const token = `refresh-${String(++this.counter)}`
    this.refreshTokens.set(token, user)
    return token
  }

  private issueAccess(user: Me): string {
    const token = `access-${String(++this.counter)}`
    this.accessTokens.set(token, user)
    return token
  }

  private tokens(user: Me): Response {
    this.cookie = this.issueRefresh(user)
    return json(200, {
      access_token: this.issueAccess(user),
      token_type: "bearer",
      expires_in: 900,
    })
  }

  private authenticated(authorization: string | null): Me | null {
    const token = authorization?.replace(/^Bearer /, "")
    return token ? (this.accessTokens.get(token) ?? null) : null
  }

  private handle(
    method: string,
    path: string,
    query: URLSearchParams,
    authorization: string | null,
    body: BodyInit | null | undefined
  ): Response {
    const route = `${method} ${path}`

    if (route === "GET /health") return json(200, { status: "ok", database: "ok" })

    if (route === "POST /auth/login") {
      if (typeof body !== "string") return error(422, "validation_error")
      const credentials = JSON.parse(body) as Schemas["LoginRequest"]
      const user = this.users.find((candidate) => candidate.email === credentials.email)
      if (!user || credentials.password !== TEST_PASSWORD) return error(401, "invalid_credentials")
      return this.tokens(user)
    }

    if (route === "POST /auth/refresh") {
      if (this.rotateRaceOnNextRefresh) {
        this.rotateRaceOnNextRefresh = false
        return error(401, "refresh_token_rotated")
      }
      const user = this.cookie ? this.refreshTokens.get(this.cookie) : undefined
      if (!this.cookie || !user) {
        this.cookie = null
        return error(401, "invalid_refresh_token")
      }
      this.refreshTokens.delete(this.cookie)
      return this.tokens(user)
    }

    const user = this.authenticated(authorization)
    if (!user) return error(401, authorization ? "invalid_token" : "not_authenticated")

    if (route === "POST /auth/logout") {
      if (this.cookie) this.refreshTokens.delete(this.cookie)
      this.cookie = null
      return new Response(null, { status: 204 })
    }
    if (route === "GET /auth/me") return json(200, user)
    if (route === "GET /organizations") {
      if (!user.permissions.includes("organizations:read")) return error(403, "permission_denied")
      if (this.failOrganizations) return error(500, "internal_error")
      return json(200, this.organizations)
    }
    if (route === "GET /dashboard/summary") {
      if (this.failDashboard) return error(500, "internal_error")
      return json(200, {
        generated_at: "2026-10-07T10:00:00Z",
        incidents: this.incidents.summary(),
        resources: this.resources.summary(),
      })
    }
    return (
      this.assignments.handle(method, path, query, user, body) ??
      this.incidents.handle(method, path, query, user, body) ??
      this.resources.handle(method, path, query, user, body) ??
      error(404, "not_found")
    )
  }
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

function error(status: number, detail: string): Response {
  return json(status, { detail })
}

export function installFakeBackend(): FakeBackend {
  const backend = new FakeBackend()
  vi.stubGlobal("fetch", backend.fetch)
  return backend
}
