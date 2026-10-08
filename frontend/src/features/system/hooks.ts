import { useQuery } from "@tanstack/react-query"

import { ApiError, apiRequest } from "@/lib/api-client"
import { queryKeys } from "@/lib/query-keys"
import type { components } from "@/types/api"

type HealthResponse = components["schemas"]["HealthResponse"]

export type ConnectionState = "online" | "degraded" | "offline"

const HEALTH_POLL_MS = 15_000

async function fetchConnectionState(): Promise<ConnectionState> {
  try {
    const health = await apiRequest<HealthResponse>("/health", { auth: false })
    return health.status === "ok" ? "online" : "degraded"
  } catch (error) {
    // 503: el backend responde pero alguna dependencia (base de datos) no.
    if (error instanceof ApiError && error.status === 503) return "degraded"
    return "offline"
  }
}

/** Estado de conexión con el backend, consultado periódicamente (público). */
export function useConnectionState() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: fetchConnectionState,
    refetchInterval: HEALTH_POLL_MS,
    retry: false,
  })
}
