/** Claves de TanStack Query centralizadas. */
export const queryKeys = {
  session: ["auth", "session"] as const,
  /** Motivo del último fin de sesión: `logout` (explícito) o `expired`. */
  sessionEndReason: ["auth", "session-end-reason"] as const,
  health: ["system", "health"] as const,
  organizations: ["organizations"] as const,
  incidentTypes: ["incident-types"] as const,
  /** Prefijo común: invalidarlo refresca listados, detalles e historiales. */
  incidents: ["incidents"] as const,
  incidentList: (params: Record<string, unknown>) => ["incidents", "list", params] as const,
  incidentMap: (params: Record<string, unknown>) => ["incidents", "map", params] as const,
  incident: (id: string) => ["incidents", "detail", id] as const,
  incidentEvents: (id: string) => ["incidents", "detail", id, "events"] as const,
  resourceTypes: ["resource-types"] as const,
  /** Prefijo común: invalidarlo refresca listados y fichas de recursos. */
  resources: ["resources"] as const,
  resourceList: (params: Record<string, unknown>) => ["resources", "list", params] as const,
  resource: (id: string) => ["resources", "detail", id] as const,
  dashboard: ["dashboard", "summary"] as const,
}
