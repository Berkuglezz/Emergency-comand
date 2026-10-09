import { useQueryClient } from "@tanstack/react-query"
import { RotateCw } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useSearchParams } from "react-router"

import { KpiTile, type KpiTileState } from "@/components/ops/kpi-tile"
import { Button } from "@/components/ui/button"
import { formatNumber, formatTime } from "@/lib/format"
import { queryKeys } from "@/lib/query-keys"
import { usePersistedToggle } from "@/lib/use-persisted-toggle"

import { useDashboardSummary } from "../hooks"
import { ActiveIncidentsPanel } from "./active-incidents-panel"
import { Dock } from "./dock"
import { IncidentMapPanel } from "./incident-map-panel"
import { IncidentSidePanel } from "./incident-side-panel"
import { ResourcesSummaryPanel } from "./resources-summary-panel"

/**
 * Centro de mando con el mapa como protagonista: una franja de indicadores y,
 * debajo, el mapa entre dos columnas plegables (incidentes activos a la
 * izquierda; incidente seleccionado, sus recursos y el resumen de recursos a la
 * derecha). La selección y los filtros viven en la URL (`/?incident=…`) y los
 * comparten el mapa, la lista y el panel; el plegado es una preferencia local.
 */
export function CommandCenterPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const summary = useDashboardSummary()
  const selectedId = searchParams.get("incident")
  const [listOpen, setListOpen] = usePersistedToggle("incidents", true)
  const [detailOpen, setDetailOpen] = usePersistedToggle("detail", true)

  const select = (id: string | null) => {
    const next = new URLSearchParams(searchParams)
    if (id) next.set("incident", id)
    else next.delete("incident")
    setSearchParams(next)
    // Elegir un incidente (en el mapa o en la lista) muestra siempre su detalle.
    if (id) setDetailOpen(true)
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
  const listTitle = t("commandCenter.incidents.title")
  const detailTitle = t("commandCenter.dock.detail")

  return (
    <div className="flex min-h-full flex-col gap-2 lg:h-full">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <h1 className="text-sm font-semibold">{t("commandCenter.title")}</h1>
        <section
          aria-label={t("commandCenter.kpis.label")}
          className="flex min-w-0 flex-1 flex-wrap gap-1.5"
        >
          <KpiTile
            variant="compact"
            label={t("commandCenter.kpis.activeIncidents")}
            value={incidents?.active_total}
            state={kpiState}
          />
          <KpiTile
            variant="compact"
            label={t("commandCenter.kpis.critical")}
            value={critical}
            // Solo se colorea si hay críticos: el color comunica estado, no decora.
            tone={critical ? "critical" : undefined}
            state={kpiState}
          />
          <KpiTile
            variant="compact"
            label={t("commandCenter.kpis.reported24h")}
            value={incidents?.reported_last_24h}
            state={kpiState}
          />
          <KpiTile
            variant="compact"
            label={t("commandCenter.kpis.affectedPeople")}
            value={incidents?.affected_people}
            state={kpiState}
          />
          <KpiTile
            variant="compact"
            label={t("commandCenter.kpis.available")}
            value={resources?.by_status.available}
            tone="ok"
            state={kpiState}
          />
          <KpiTile
            variant="compact"
            label={t("commandCenter.kpis.inService")}
            value={resources?.by_status.in_service}
            tone="info"
            state={kpiState}
          />
        </section>
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

      <div className="flex min-h-0 flex-1 flex-col gap-2 lg:flex-row">
        <Dock
          side="left"
          open={listOpen}
          onOpenChange={setListOpen}
          label={listTitle}
          widthClassName="lg:w-72 xl:w-80 2xl:w-96"
          summary={
            incidents && (
              <span
                className="font-data text-xs font-semibold"
                title={t("commandCenter.dock.activeCount", { count: incidents.active_total })}
              >
                <span aria-hidden>{formatNumber(incidents.active_total)}</span>
                <span className="sr-only">
                  {t("commandCenter.dock.activeCount", { count: incidents.active_total })}
                </span>
              </span>
            )
          }
        >
          <ActiveIncidentsPanel
            selectedId={selectedId}
            onSelect={select}
            onCollapse={() => {
              setListOpen(false)
            }}
            className="h-96 lg:h-auto lg:flex-1"
          />
        </Dock>

        <IncidentMapPanel
          selectedId={selectedId}
          onSelect={select}
          className="order-2 h-[60vh] min-h-80 lg:h-auto lg:min-h-0 lg:flex-1"
        />

        <Dock
          side="right"
          open={detailOpen}
          onOpenChange={setDetailOpen}
          label={detailTitle}
          widthClassName="lg:w-80 xl:w-[22rem] 2xl:w-[26rem]"
        >
          {/* Una sola barra de desplazamiento para toda la columna. */}
          <div className="flex min-h-0 flex-1 flex-col gap-2 *:shrink-0 lg:overflow-y-auto">
            <IncidentSidePanel
              incidentId={selectedId}
              onClose={() => {
                select(null)
              }}
              onCollapse={() => {
                setDetailOpen(false)
              }}
            />
            <ResourcesSummaryPanel
              summary={summary.data?.resources}
              status={kpiState === "ready" ? "ready" : kpiState}
              onRetry={() => void summary.refetch()}
            />
          </div>
        </Dock>
      </div>
    </div>
  )
}
