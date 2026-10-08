import { type QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"

import { useSessionExpiredHandler } from "@/features/auth/hooks"

function SessionExpiredBridge() {
  useSessionExpiredHandler()
  return null
}

export function AppProviders({
  queryClient,
  children,
}: {
  queryClient: QueryClient
  children: ReactNode
}) {
  return (
    <QueryClientProvider client={queryClient}>
      <SessionExpiredBridge />
      {children}
    </QueryClientProvider>
  )
}
