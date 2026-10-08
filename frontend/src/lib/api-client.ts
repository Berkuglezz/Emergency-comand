/**
 * Cliente HTTP de la API. Único lugar que gestiona tokens y refresh.
 *
 * - El access token vive solo en memoria (esta variable de módulo). Nunca en
 *   localStorage ni sessionStorage (CLAUDE.md §6).
 * - El refresh token viaja en una cookie httpOnly que JavaScript no puede leer;
 *   el navegador la envía sola a /api/v1/auth/*.
 * - Ante un 401 se hace un único refresh compartido entre todas las peticiones
 *   en curso y se reintenta la petición una sola vez.
 * - Si el refresh falla de forma definitiva, se borra el token y se notifica
 *   «sesión expirada» para volver al login.
 * - Nunca se registra un token, una cookie ni una credencial.
 */

const API_BASE = "/api/v1"
const REFRESH_PATH = "/auth/refresh"

// --- Access token en memoria ------------------------------------------------

let accessToken: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string): void {
  accessToken = token
}

export function clearAccessToken(): void {
  accessToken = null
}

// --- Sesión expirada ------------------------------------------------------------

type Listener = () => void
const sessionExpiredListeners = new Set<Listener>()

/** Se llama cuando el refresh falla de forma definitiva. Devuelve la baja. */
export function onSessionExpired(listener: Listener): () => void {
  sessionExpiredListeners.add(listener)
  return () => {
    sessionExpiredListeners.delete(listener)
  }
}

function expireSession(): void {
  clearAccessToken()
  for (const listener of sessionExpiredListeners) listener()
}

// --- Errores ---------------------------------------------------------------------

/** Error de la API. `code` es el código estable del backend (`detail`). */
export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string) {
    super(code)
    this.name = "ApiError"
    this.status = status
    this.code = code
  }

  get isNetworkError(): boolean {
    return this.status === 0
  }
}

/** 409 `version_conflict`: otra persona modificó el registro (bloqueo optimista). */
export function isVersionConflict(error: unknown): boolean {
  return error instanceof ApiError && error.code === "version_conflict"
}

async function readErrorCode(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (typeof body === "object" && body !== null && "detail" in body) {
      const { detail } = body
      // FastAPI devuelve un array en los errores de validación (422).
      if (typeof detail === "string") return detail
      if (Array.isArray(detail)) return "validation_error"
    }
  } catch {
    // Cuerpo vacío o no JSON.
  }
  return response.status >= 500 ? "server_error" : "unknown_error"
}

// --- Refresh compartido -----------------------------------------------------

type RefreshResult = "refreshed" | "expired"

let refreshInFlight: Promise<RefreshResult> | null = null

async function requestRefresh(): Promise<Response> {
  try {
    return await fetch(`${API_BASE}${REFRESH_PATH}`, {
      method: "POST",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
  } catch {
    throw new ApiError(0, "network_error")
  }
}

async function performRefresh(): Promise<RefreshResult> {
  let response = await requestRefresh()

  // Otra pestaña acaba de rotar el token: la cookie ya contiene el nuevo.
  // Se reintenta una sola vez (sin bucles).
  if (
    response.status === 401 &&
    (await readErrorCode(response.clone())) === "refresh_token_rotated"
  ) {
    response = await requestRefresh()
  }

  if (response.ok) {
    const body = (await response.json()) as { access_token: string }
    setAccessToken(body.access_token)
    return "refreshed"
  }
  if (response.status === 401) {
    expireSession()
    return "expired"
  }
  // 5xx u otros: fallo transitorio. No se cierra la sesión.
  throw new ApiError(response.status, await readErrorCode(response))
}

/**
 * Renueva el access token con la cookie de refresh. Las llamadas simultáneas
 * comparten la misma petición. Devuelve `true` si hay un token nuevo.
 */
export async function refreshAccessToken(): Promise<boolean> {
  refreshInFlight ??= performRefresh().finally(() => {
    refreshInFlight = null
  })
  return (await refreshInFlight) === "refreshed"
}

// --- Peticiones ---------------------------------------------------------------

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  body?: unknown
  /** `false` en endpoints públicos (login, health): un 401 no intenta refresh. */
  auth?: boolean
  signal?: AbortSignal
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" }
  if (options.body !== undefined) headers["Content-Type"] = "application/json"
  const token = getAccessToken()
  if (options.auth !== false && token) headers.Authorization = `Bearer ${token}`

  try {
    return await fetch(`${API_BASE}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: "same-origin",
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error
    throw new ApiError(0, "network_error")
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options)

  if (response.status === 401 && options.auth !== false) {
    // Un único refresh y un único reintento: nunca hay bucles.
    if (await refreshAccessToken()) {
      response = await send(path, options)
      if (response.status === 401) expireSession()
    }
  }

  if (!response.ok) throw new ApiError(response.status, await readErrorCode(response))
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
