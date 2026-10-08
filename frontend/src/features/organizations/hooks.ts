import { useQuery } from "@tanstack/react-query"

import { apiRequest } from "@/lib/api-client"
import { queryKeys } from "@/lib/query-keys"
import type { components } from "@/types/api"

export type Organization = components["schemas"]["OrganizationResponse"]

/** `enabled: false` cuando el usuario no tiene `organizations:read` (evita un 403 seguro). */
export function useOrganizations({ enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.organizations,
    queryFn: ({ signal }) => apiRequest<Organization[]>("/organizations", { signal }),
    enabled,
  })
}
