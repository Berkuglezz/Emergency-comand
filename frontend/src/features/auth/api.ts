import { apiRequest, getAccessToken, refreshAccessToken, setAccessToken } from "@/lib/api-client"

import type { LoginRequest, SessionUser, TokenResponse } from "./types"

export async function login(credentials: LoginRequest): Promise<void> {
  // Endpoint público: un 401 aquí son credenciales incorrectas, no un token caducado.
  const tokens = await apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body: credentials,
    auth: false,
  })
  setAccessToken(tokens.access_token)
}

export function fetchCurrentUser(): Promise<SessionUser> {
  return apiRequest<SessionUser>("/auth/me")
}

/**
 * Restaura la sesión al cargar la aplicación: si no hay access token en
 * memoria (p. ej. tras recargar la página), intenta un refresh silencioso con
 * la cookie. Devuelve `null` si no hay sesión.
 */
export async function restoreSession(): Promise<SessionUser | null> {
  if (!getAccessToken() && !(await refreshAccessToken())) return null
  return fetchCurrentUser()
}

export function logout(): Promise<void> {
  return apiRequest<undefined>("/auth/logout", { method: "POST" })
}
