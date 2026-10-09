import { FolderTree, Siren, Truck } from "lucide-react"
import { useId } from "react"
import { useTranslation } from "react-i18next"
import { Link, useSearchParams } from "react-router"

import { FilterSelect } from "@/components/ops/filter-select"
import { Panel, type PanelStatus } from "@/components/ops/panel"
import { PRIORITY_CODES } from "@/components/ops/priority"
import { PriorityBadge } from "@/components/ops/priority-badge"
import { SimulatedPill } from "@/components/ops/simulated-pill"
import { buttonVariants } from "@/components/ui/button"
import { IncidentStatusPill } from "@/features/incidents/components/incident-badges"
import { UnlocatedMark } from "@/features/incidents/components/unlocated-mark"
import { useIncidents } from "@/features/incidents/hooks"
import { incidentErrorMessage } from "@/features/incidents/presentation"
import { formatDateTime, formatNumber } from "@/lib/format"
import { cn } from "@/lib/utils"

import { ACTIVE_STATUS_CODES, parseCommandCenterFilters, toActiveQuery } from "../filters"
import { DockToggle } from "./dock"

const LIMIT = 50

interface ActiveIncidentsPanelProps {
  selectedId: string | null
  onSelect: (id: string) => void
  /** Pliega la columna que contiene el panel. */
  onCollapse: () => void
  className?: string
}

/**
 * Incidentes activos por prioridad, en filas compactas para una columna
 * lateral, con filtros básicos y selección. Toda la fila selecciona.
 */
export function ActiveIncidentsPanel({
  selectedId,
  onSelect,
  onCollapse,
  className,
}: ActiveIncidentsPanelProps) {
  const { t } = useTranslation()
  const id = useId()
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = parseCommandCenterFilters(searchParams)
  const { priority, status } = filters
  const incidents = useIncidents({ ...toActiveQuery(filters), sort: "priority", limit: LIMIT })

  const setFilter = (key: "priority" | "status", value: string) => {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    setSearchParams(next)
  }

  let panelStatus: PanelStatus = "ready"
  if (incidents.isPending) panelStatus = "loading"
  else if (incidents.isError) panelStatus = "error"
  else if (incidents.data.items.length === 0) panelStatus = "empty"
  const page = incidents.data

  return (
    <Panel
      title={t("commandCenter.incidents.title")}
      description={
        page && page.total > 0
          ? t("incidents.list.range", {
              from: formatNumber(1),
              to: formatNumber(page.items.length),
              total: formatNumber(page.total),
            })
          : undefined
      }
      actions={
        <>
          <Link to="/incidents" className={buttonVariants({ variant: "ghost", size: "sm" })}>
            {t("commandCenter.incidents.viewAll")}
          </Link>
          <DockToggle
            side="left"
            open
            label={t("commandCenter.incidents.title")}
            onOpenChange={onCollapse}
          />
        </>
      }
      status={panelStatus}
      empty={{
        icon: Siren,
        description:
          priority || status
            ? t("commandCenter.incidents.emptyFiltered")
            : t("commandCenter.incidents.empty"),
      }}
      error={{
        description: incidentErrorMessage(incidents.error, t),
        onRetry: () => void incidents.refetch(),
      }}
      flush
      className={className}
    >
      <div className="grid grid-cols-2 gap-2 border-b px-3 py-2">
        <FilterSelect
          id={`${id}-priority`}
          label={t("incidents.filters.priority")}
          value={priority ?? ""}
          onChange={(value) => {
            setFilter("priority", value)
          }}
          options={PRIORITY_CODES.map((code) => ({ value: code, label: t(`priority.${code}`) }))}
          className="w-full"
        />
        <FilterSelect
          id={`${id}-status`}
          label={t("incidents.filters.status")}
          value={status ?? ""}
          onChange={(value) => {
            setFilter("status", value)
          }}
          options={ACTIVE_STATUS_CODES.map((code) => ({
            value: code,
            label: t(`incidentStatus.${code}`),
          }))}
          className="w-full"
        />
      </div>
      <ul aria-label={t("commandCenter.incidents.title")} className="flex flex-col divide-y">
        {page?.items.map((incident) => {
          const selected = incident.id === selectedId
          return (
            <li
              key={incident.id}
              data-state={selected ? "selected" : undefined}
              className={cn(
                "relative flex flex-col gap-1 border-l-2 py-1.5 pr-3 pl-2.5 hover:bg-surface-2",
                selected ? "border-l-info bg-surface-2" : "border-l-transparent"
              )}
            >
              <div className="flex min-w-0 items-center gap-1.5">
                <PriorityBadge priority={incident.priority} pulse />
                {/* Selecciona sin salir del centro de mando. El botón cubre toda la
                    fila (`after:`), pero su nombre accesible sigue siendo el código. */}
                <button
                  type="button"
                  aria-pressed={selected}
                  aria-label={t("commandCenter.incidents.select", { code: incident.code })}
                  // El botón cubre la fila: su tooltip muestra el título completo.
                  title={incident.title}
                  onClick={() => {
                    onSelect(incident.id)
                  }}
                  className="rounded-sm font-data font-medium outline-none after:absolute after:inset-0 after:content-[''] hover:underline focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  {incident.code}
                </button>
                {incident.is_simulated && <SimulatedPill />}
                <span className="ml-auto shrink-0">
                  <IncidentStatusPill status={incident.status} />
                </span>
              </div>
              <div className="flex min-w-0 items-center gap-1.5">
                {incident.parent_incident_id && (
                  <FolderTree
                    aria-label={t("incidents.list.child")}
                    className="size-3.5 shrink-0 text-muted-foreground"
                  />
                )}
                <span className="truncate font-medium">{incident.title}</span>
              </div>
              <div className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
                <span className="flex min-w-0 items-center gap-1">
                  <span className="truncate">{incident.location.municipality}</span>
                  {incident.location.latitude === null && <UnlocatedMark />}
                </span>
                {incident.active_assignments > 0 && (
                  <span
                    className="inline-flex shrink-0 items-center gap-0.5 font-data text-info"
                    title={t("commandCenter.incidents.assigned", {
                      count: incident.active_assignments,
                    })}
                  >
                    <Truck aria-hidden className="size-3.5" />
                    <span aria-hidden>{incident.active_assignments}</span>
                    <span className="sr-only">
                      {t("commandCenter.incidents.assigned", {
                        count: incident.active_assignments,
                      })}
                    </span>
                  </span>
                )}
                <time dateTime={incident.reported_at} className="ml-auto shrink-0 font-data">
                  {formatDateTime(incident.reported_at)}
                </time>
              </div>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}
