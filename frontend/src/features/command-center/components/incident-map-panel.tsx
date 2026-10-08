import { CircleCheck, FlaskConical, MapPinOff, TriangleAlert } from "lucide-react"
import { Suspense } from "react"
import { useTranslation } from "react-i18next"
import { Link, useSearchParams } from "react-router"

import { MARKER_BORDER_CLASS, MARKER_STATUS_STYLE } from "@/components/ops/marker-style"
import { Panel } from "@/components/ops/panel"
import { PRIORITY_CODES } from "@/components/ops/priority"
import { PriorityBadge } from "@/components/ops/priority-badge"
import { StatusPill } from "@/components/ops/status-pill"
import { Skeleton } from "@/components/ui/skeleton"
import { useIncident, useIncidentMap } from "@/features/incidents/hooks"
import { incidentErrorMessage } from "@/features/incidents/presentation"
import { IncidentsMap } from "@/features/map/lazy"
import { formatNumber } from "@/lib/format"
import { cn } from "@/lib/utils"

import { parseCommandCenterFilters, toActiveQuery } from "../filters"

interface IncidentMapPanelProps {
  selectedId: string | null
  onSelect: (id: string) => void
  className?: string
}

/**
 * Mapa del centro de mando: incidentes activos con coordenadas, con los
 * mismos filtros que la lista (URL). Los que no tienen coordenadas no se
 * ocultan: se cuentan y se enlazan al listado.
 */
export function IncidentMapPanel({ selectedId, onSelect, className }: IncidentMapPanelProps) {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const map = useIncidentMap(toActiveQuery(parseCommandCenterFilters(searchParams)))
  // Misma consulta que el panel lateral (caché compartida): ¿tiene coordenadas?
  const selected = useIncident(selectedId ?? "", { enabled: selectedId !== null })

  const features = map.data?.features ?? []
  const unlocated = map.data?.unlocated_total ?? 0
  const selectedUnlocated = selected.data?.location.latitude === null ? selected.data : null

  return (
    <Panel
      title={t("commandCenter.map.title")}
      description={
        map.data
          ? t("commandCenter.map.count", {
              count: features.length,
              formatted: formatNumber(features.length),
            })
          : undefined
      }
      status={map.isError ? "error" : "ready"}
      error={{
        description: incidentErrorMessage(map.error, t),
        onRetry: () => void map.refetch(),
      }}
      className={className}
    >
      <div className="flex min-h-0 flex-1 flex-col gap-2">
        <Suspense fallback={<Skeleton className="min-h-56 flex-1" />}>
          <IncidentsMap
            features={features}
            selectedId={selectedId}
            onSelect={onSelect}
            className="min-h-56 flex-1"
            overlay={
              <div className="absolute top-2 left-2 z-10 flex max-w-[calc(100%-4rem)] flex-col items-start gap-1">
                {features.some((feature) => feature.properties.is_simulated) && (
                  <StatusPill tone="info" icon={FlaskConical} className="bg-surface-1">
                    {t("commandCenter.map.simulatedData")}
                  </StatusPill>
                )}
                {map.isPending && (
                  <span role="status" className="rounded-sm bg-surface-1 px-1.5 text-xs">
                    {t("common.loading")}
                  </span>
                )}
                {map.data?.truncated && (
                  <StatusPill tone="warning" icon={TriangleAlert} className="bg-surface-1">
                    {t("commandCenter.map.truncated")}
                  </StatusPill>
                )}
                {selectedUnlocated && (
                  <p className="flex items-center gap-1.5 rounded-sm border bg-surface-1 px-1.5 py-0.5 text-xs">
                    <MapPinOff aria-hidden className="size-3.5 shrink-0" />
                    {t("commandCenter.map.selectedUnlocated", { code: selectedUnlocated.code })}
                  </p>
                )}
              </div>
            }
          />
        </Suspense>

        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          {unlocated > 0 ? (
            <p className="flex items-center gap-1.5 text-warning">
              <MapPinOff aria-hidden className="size-4 shrink-0" />
              <span>
                {t("commandCenter.map.unlocated", {
                  count: unlocated,
                  formatted: formatNumber(unlocated),
                })}
              </span>
              <Link
                to="/incidents?coords=without"
                className="text-text underline underline-offset-4"
              >
                {t("commandCenter.map.viewUnlocated")}
              </Link>
            </p>
          ) : (
            <span />
          )}
          <MapLegend />
        </div>
      </div>
    </Panel>
  )
}

const LEGEND_STATUS = [
  { key: "pending", style: MARKER_STATUS_STYLE.received },
  { key: "active", style: MARKER_STATUS_STYLE.in_progress },
] as const

/** Leyenda plegable (abierta por defecto) de la codificación de los marcadores. */
function MapLegend() {
  const { t } = useTranslation()
  return (
    <details open className="text-xs">
      <summary className="cursor-pointer text-muted-foreground">
        {t("commandCenter.map.legend.title")}
      </summary>
      <div className="mt-1.5 flex flex-col gap-1.5">
        <ul aria-label={t("commandCenter.map.legend.priority")} className="flex flex-wrap gap-1">
          {PRIORITY_CODES.map((priority) => (
            <li key={priority}>
              <PriorityBadge priority={priority} />
            </li>
          ))}
        </ul>
        <ul aria-label={t("commandCenter.map.legend.status")} className="flex flex-wrap gap-3">
          {LEGEND_STATUS.map(({ key, style }) => (
            <li key={key} className="flex items-center gap-1.5">
              <span
                aria-hidden
                className={cn("size-3.5 rounded-sm border-2", MARKER_BORDER_CLASS[style])}
              />
              {t(`commandCenter.map.legend.${key}`)}
            </li>
          ))}
          <li className="flex items-center gap-1.5">
            <CircleCheck aria-hidden className="size-3.5 text-ok" />
            {t("commandCenter.map.legend.controlled")}
          </li>
        </ul>
      </div>
    </details>
  )
}
