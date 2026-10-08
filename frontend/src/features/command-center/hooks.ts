import { useQuery } from "@tanstack/react-query"

import { queryKeys } from "@/lib/query-keys"

import { fetchDashboardSummary } from "./api"

/**
 * KPIs del centro de mando. Sin tiempo real ni sondeo periódico (fases
 * posteriores): se refrescan tras cada escritura (invalidación) o con
 * «Actualizar». `generated_at` dice de cuándo son los datos.
 */
export function useDashboardSummary() {
  return useQuery({
    queryKey: queryKeys.dashboard,
    queryFn: ({ signal }) => fetchDashboardSummary(signal),
  })
}
