import { useQueryClient } from "@tanstack/react-query"
import { Map as MapIcon, RotateCw } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useSearchParams } from "react-router"

import { KpiTile, type KpiTileState } from "@/components/ops/kpi-tile"
import { Panel } from "@/components/ops/panel"
import { Button } from "@/components/ui/button"
import { formatTime } from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"

import { useDashboardSummary } from "../hooks"
import { ActiveIncidentsPanel } from "./active-incidents-panel"
import { IncidentSidePanel } from "./incident-side-panel"
import { ResourcesSummaryPanel } from "./resources-summary-panel"

/**
 * Centro de mando con datos reales: KPIs, incidentes activos, incidente
 * seleccionado y resumen de recursos. El mapa sigue reservado (fase posterior).
 * La selección y los filtros viven en la URL (`/?incident=…&priority=…`).
 */
export function CommandCenterPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const summary = useDashboardSummary()
  const selectedId = searchParams.get("incident")

  const select = (id: string | null) => {
    const next = new URLSearchParams(searchParams)
    if (id) next.set("incident", id)
    else next.delete("incident")
    setSearchParams(next)
  }

  // Refresco manual: KPIs, listados y el incidente seleccionado.
  const refresh = () => {
    for (const queryKey of [queryKeys.dashboard, queryKeys.incidents, queryKeys.resources]) {
      void queryClient.invalidateQueries({ queryKey })
    }
  }

  let kpiState: KpiTileState = "ready"
  if (summary.isPending) kpiState = "loading"
  else if (summary.isError) kpiState = "error"
  const incidents = summary.data?.incidents
  const resources = summary.data?.resources
  const critical = incidents?.by_priority.critical

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold">{t("commandCenter.title")}</h1>
        <div className="flex items-center gap-2">
          {summary.data && (
            <span className="font-data text-xs text-muted-foreground">
              {t("commandCenter.dataAt", { time: formatTime(new Date(summary.data.generated_at)) })}
            </span>
          )}
          <Button variant="outline" size="sm" disabled={summary.isFetching} onClick={refresh}>
            <RotateCw data-icon="inline-start" aria-hidden />
            {t("common.refresh")}
          </Button>
        </div>
      </header>

      <section aria-label={t("commandCenter.kpis.label")} className="flex flex-wrap gap-2">
        <KpiTile
          label={t("commandCenter.kpis.activeIncidents")}
          value={incidents?.active_total}
          state={kpiState}
        />
        <KpiTile
          label={t("commandCenter.kpis.critical")}
          value={critical}
          // Solo se colorea si hay críticos: el color comunica estado, no decora.
          tone={critical ? "critical" : undefined}
          state={kpiState}
        />
        <KpiTile
          label={t("commandCenter.kpis.reported24h")}
          value={incidents?.reported_last_24h}
          state={kpiState}
        />
        <KpiTile
          label={t("commandCenter.kpis.affectedPeople")}
          value={incidents?.affected_people}
          state={kpiState}
        />
        <KpiTile
          label={t("commandCenter.kpis.available")}
          value={resources?.by_status.available}
          tone="ok"
          state={kpiState}
        />
        <KpiTile
          label={t("commandCenter.kpis.inService")}
          value={resources?.by_status.in_service}
          tone="info"
          state={kpiState}
        />
      </section>

      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(320px,380px)]">
        <div className="flex min-h-0 min-w-0 flex-col gap-3">
          <Panel
            title={t("commandCenter.map.title")}
            status="empty"
            empty={{ icon: MapIcon, description: t("commandCenter.map.empty") }}
            className="min-h-48 lg:h-60 lg:shrink-0"
          />
          <ActiveIncidentsPanel
            selectedId={selectedId}
            onSelect={select}
            className="min-h-80 flex-1"
          />
        </div>
        <div className="flex min-h-0 min-w-0 flex-col gap-3">
          <IncidentSidePanel
            incidentId={selectedId}
            onClose={() => {
              select(null)
            }}
            className="min-h-64 flex-1"
          />
          <ResourcesSummaryPanel
            summary={summary.data?.resources}
            status={kpiState === "ready" ? "ready" : kpiState}
            onRetry={() => void summary.refetch()}
          />
        </div>
      </div>
    </div>
  )
}
