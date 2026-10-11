import {
  CircleCheck,
  FlaskConical,
  MapPin,
  MapPinOff,
  RotateCw,
  Shapes,
  TriangleAlert,
} from "lucide-react"
import { Suspense, useId } from "react"
import { useTranslation } from "react-i18next"
import { Link, useSearchParams } from "react-router"

import { MARKER_BORDER_CLASS, MARKER_STATUS_STYLE } from "@/components/ops/marker-style"
import { PRIORITY_CODES } from "@/components/ops/priority"
import { PriorityBadge } from "@/components/ops/priority-badge"
import { StatusPill } from "@/components/ops/status-pill"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useAssignments } from "@/features/assignments/hooks"
import { useIncident, useIncidentMap } from "@/features/incidents/hooks"
import { incidentErrorMessage } from "@/features/incidents/presentation"
import { IncidentsMap } from "@/features/map/lazy"
import { useIncidentPerimeters } from "@/features/map-features/hooks"
import type { MapBase } from "@/features/map/incidents-map"
import { useCodeLabel } from "@/lib/code-label"
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
 * mismos filtros que la lista (URL). Ocupa toda su zona, sin cabecera ni pie:
 * recuento, avisos y leyenda van superpuestos en las esquinas. Los incidentes
 * sin coordenadas no se ocultan: se cuentan y se enlazan al listado.
 */
export function IncidentMapPanel({ selectedId, onSelect, className }: IncidentMapPanelProps) {
  const { t } = useTranslation()
  const titleId = useId()
  const [searchParams] = useSearchParams()
  const map = useIncidentMap(toActiveQuery(parseCommandCenterFilters(searchParams)))
  // Misma consulta que el panel lateral (caché compartida): ¿tiene coordenadas?
  const selected = useIncident(selectedId ?? "", { enabled: selectedId !== null })
  const label = useCodeLabel()
  // Bases de los recursos asignados al incidente seleccionado (solo esas).
  const assignments = useAssignments(selectedId ?? "", { enabled: selectedId !== null })
  // Perímetros guardados del incidente seleccionado (misma consulta que el panel lateral).
  const perimeters = useIncidentPerimeters(selectedId)
  // Varios recursos pueden compartir base: un marcador por punto.
  const bases = new Map<string, MapBase>()
  for (const assignment of assignments.data ?? []) {
    const { base } = assignment.resource
    if (assignment.released_at !== null || base.latitude === null || base.longitude === null)
      continue
    const key = `${String(base.longitude)},${String(base.latitude)}`
    const entry = bases.get(key) ?? {
      id: key,
      items: [],
      position: [base.longitude, base.latitude],
    }
    entry.items.push({
      code: assignment.resource.code,
      typeLabel: label("resourceTypes", assignment.resource.type.code),
      etaLabel: assignment.eta
        ? t("ops.eta.short", {
            minutes: formatNumber(assignment.eta.minutes),
            distance: formatNumber(assignment.eta.distance_km),
          })
        : t("ops.eta.none"),
    })
    bases.set(key, entry)
  }

  const features = map.data?.features ?? []
  const unlocated = map.data?.unlocated_total ?? 0
  const selectedUnlocated = selected.data?.location.latitude === null ? selected.data : null

  return (
    <section
      aria-labelledby={titleId}
      className={cn("relative flex min-h-0 min-w-0 flex-col", className)}
    >
      {/* El título no se ve (el mapa habla por sí mismo), pero estructura la página. */}
      <h2 id={titleId} className="sr-only">
        {t("commandCenter.map.title")}
      </h2>
      <Suspense fallback={<Skeleton className="min-h-56 flex-1" />}>
        <IncidentsMap
          features={features}
          bases={selectedId ? [...bases.values()] : []}
          perimeters={perimeters.data}
          selectedId={selectedId}
          onSelect={onSelect}
          className="min-h-56 flex-1"
          overlay={
            <>
              <div className="pointer-events-none absolute top-2 left-2 z-10 flex max-w-[calc(100%-4rem)] flex-col items-start gap-1 *:pointer-events-auto">
                <div className="flex flex-wrap items-center gap-1">
                  {map.data && (
                    <span className="inline-flex h-6 items-center gap-1.5 rounded-md border bg-surface-1/95 px-2 text-xs">
                      <MapPin aria-hidden className="size-3.5 text-muted-foreground" />
                      {t("commandCenter.map.count", {
                        count: features.length,
                        formatted: formatNumber(features.length),
                      })}
                    </span>
                  )}
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
                  {perimeters.isLoading && (
                    <span role="status" className="rounded-sm bg-surface-1 px-1.5 text-xs">
                      {t("commandCenter.map.perimeterLoading")}
                    </span>
                  )}
                  {/* Siempre «Dibujado · no validado» (D-M5): no es un dato oficial. */}
                  {perimeters.data && perimeters.data.length > 0 && (
                    <StatusPill tone="warning" icon={Shapes} className="bg-surface-1">
                      {t("commandCenter.map.perimeterShown", { count: perimeters.data.length })}
                    </StatusPill>
                  )}
                  {map.data?.truncated && (
                    <StatusPill tone="warning" icon={TriangleAlert} className="bg-surface-1">
                      {t("commandCenter.map.truncated")}
                    </StatusPill>
                  )}
                </div>
                {unlocated > 0 && (
                  <p className="flex items-center gap-1.5 rounded-md border border-warning-border bg-surface-1/95 px-2 py-0.5 text-xs text-warning">
                    <MapPinOff aria-hidden className="size-3.5 shrink-0" />
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
                )}
                {selectedUnlocated && (
                  <p className="flex items-center gap-1.5 rounded-md border bg-surface-1/95 px-2 py-0.5 text-xs">
                    <MapPinOff aria-hidden className="size-3.5 shrink-0" />
                    {t("commandCenter.map.selectedUnlocated", { code: selectedUnlocated.code })}
                  </p>
                )}
                {perimeters.isError && (
                  <p className="flex items-center gap-1.5 rounded-md border border-warning-border bg-surface-1/95 px-2 py-0.5 text-xs">
                    <TriangleAlert aria-hidden className="size-3.5 shrink-0 text-warning" />
                    {t("commandCenter.map.perimeterError")}
                    <Button variant="outline" size="xs" onClick={() => void perimeters.refetch()}>
                      {t("common.retry")}
                    </Button>
                  </p>
                )}
                {map.isError && (
                  <Alert variant="destructive" className="w-auto max-w-sm bg-surface-1">
                    <TriangleAlert aria-hidden />
                    <AlertTitle>{t("ops.panel.errorTitle")}</AlertTitle>
                    <AlertDescription>
                      <p>{incidentErrorMessage(map.error, t)}</p>
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-2"
                        onClick={() => void map.refetch()}
                      >
                        <RotateCw data-icon="inline-start" aria-hidden />
                        {t("common.retry")}
                      </Button>
                    </AlertDescription>
                  </Alert>
                )}
              </div>
              <MapLegend />
            </>
          }
        />
      </Suspense>
    </section>
  )
}

const LEGEND_STATUS = [
  { key: "pending", style: MARKER_STATUS_STYLE.received },
  { key: "active", style: MARKER_STATUS_STYLE.in_progress },
] as const

/**
 * Leyenda de la codificación de los marcadores, superpuesta abajo a la
 * izquierda. Plegada por defecto para no tapar el mapa; se abre con un clic.
 */
function MapLegend() {
  const { t } = useTranslation()
  return (
    <details className="absolute bottom-2 left-2 z-10 max-w-[calc(100%-6rem)] rounded-md border bg-surface-1/95 px-2 py-1 text-xs">
      <summary className="cursor-pointer rounded-sm text-muted-foreground outline-none hover:text-text focus-visible:ring-3 focus-visible:ring-ring/50">
        {t("commandCenter.map.legend.title")}
      </summary>
      <div className="mt-1.5 mb-1 flex flex-col gap-1.5">
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
        <ul aria-label={t("commandCenter.map.legend.mapFeatures")} className="flex flex-wrap gap-3">
          <li className="flex items-center gap-1.5">
            {/* Mismo trazo que la capa: contorno discontinuo y relleno tenue. */}
            <span
              aria-hidden
              className="size-3.5 rounded-sm border-2 border-dashed border-warning bg-warning-subtle"
            />
            {t("commandCenter.map.legend.perimeter")}
          </li>
        </ul>
      </div>
    </details>
  )
}
