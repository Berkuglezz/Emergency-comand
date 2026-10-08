import { QueryClient } from "@tanstack/react-query"

import { ApiError } from "@/lib/api-client"

const MAX_RETRIES = 2

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Los errores 4xx (sin permiso, no encontrado…) no se arreglan reintentando.
        retry: (failureCount, error) =>
          failureCount < MAX_RETRIES &&
          !(error instanceof ApiError && error.status >= 400 && error.status < 500),
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  })
}
