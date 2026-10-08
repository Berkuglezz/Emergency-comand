import {
  hashKey,
  type QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { useEffect } from "react"

import { ApiError, clearAccessToken, onSessionExpired } from "@/lib/api-client"
import { queryKeys } from "@/lib/query-keys"

import { fetchCurrentUser, login, logout, restoreSession } from "./api"
import type { LoginRequest, Permission, SessionUser } from "./types"

/**
 * Sesión actual: `null` si no hay sesión. La primera carga intenta restaurarla
 * con un refresh silencioso. Los errores de red no se reintentan en bucle.
 */
export function useSession() {
  return useQuery({
    queryKey: queryKeys.session,
    queryFn: restoreSession,
    staleTime: Infinity,
    retry: false,
  })
}

export type SessionEndReason = "logout" | "expired"

/** Vacía todos los datos cacheados y deja la sesión en `null` (sin sesión). */
function endSession(queryClient: QueryClient, reason: SessionEndReason): void {
  clearAccessToken()
  const sessionHash = hashKey(queryKeys.session)
  queryClient.removeQueries({ predicate: (query) => query.queryHash !== sessionHash })
  queryClient.setQueryData(queryKeys.sessionEndReason, reason)
  queryClient.setQueryData(queryKeys.session, null)
}

/** Motivo del último fin de sesión, si lo hubo (decide si se recuerda la ruta). */
export function useSessionEndReason(): SessionEndReason | undefined {
  return useQueryClient().getQueryData<SessionEndReason>(queryKeys.sessionEndReason)
}

/** Con permiso: solo UX. La autorización real la comprueba el backend. */
export function hasPermission(
  user: SessionUser | null | undefined,
  permission: Permission
): boolean {
  return user?.permissions.includes(permission) ?? false
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (credentials: LoginRequest) => {
      await login(credentials)
      return fetchCurrentUser()
    },
    onSuccess: (user) => {
      queryClient.removeQueries({ queryKey: queryKeys.sessionEndReason })
      queryClient.setQueryData(queryKeys.session, user)
    },
  })
}

/** Cierra la sesión en el backend y en local. */
export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      try {
        await logout()
      } catch (error) {
        // Sin conexión o sesión ya caducada: se cierra igualmente en local.
        if (!(error instanceof ApiError)) throw error
      }
    },
    onSettled: () => {
      endSession(queryClient, "logout")
    },
  })
}

/**
 * Cuando el cliente API declara la sesión expirada (refresh fallido), se
 * vacía la caché y la sesión pasa a `null`: las rutas protegidas llevan al login.
 */
export function useSessionExpiredHandler(): void {
  const queryClient = useQueryClient()
  useEffect(
    () =>
      onSessionExpired(() => {
        endSession(queryClient, "expired")
      }),
    [queryClient]
  )
}
