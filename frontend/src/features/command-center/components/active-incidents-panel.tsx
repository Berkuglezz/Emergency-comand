import { FolderTree, Siren } from "lucide-react"
import { useId } from "react"
import { useTranslation } from "react-i18next"
import { Link, useSearchParams } from "react-router"

import { FilterSelect } from "@/components/ops/filter-select"
import { Panel, type PanelStatus } from "@/components/ops/panel"
import { PRIORITY_CODES } from "@/components/ops/priority"
import { PriorityBadge } from "@/components/ops/priority-badge"
import { SimulatedPill } from "@/components/ops/simulated-pill"
import { buttonVariants } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { IncidentStatusPill } from "@/features/incidents/components/incident-badges"
import { useIncidents } from "@/features/incidents/hooks"
import {
  incidentErrorMessage,
  isIrreversible,
  STATUS_CODES,
} from "@/features/incidents/presentation"
import { formatDateTime, formatNumber } from "@/lib/format"
import { oneOf } from "@/lib/query-string"

// Solo estados activos: cerrados y cancelados no aparecen en el centro de mando.
const ACTIVE_STATUS_CODES = STATUS_CODES.filter((status) => !isIrreversible(status))
const LIMIT = 50

interface ActiveIncidentsPanelProps {
  selectedId: string | null
  onSelect: (id: string) => void
  className?: string
}

/** Incidentes activos por prioridad, con filtros básicos y selección. */
export function ActiveIncidentsPanel({
  selectedId,
  onSelect,
  className,
}: ActiveIncidentsPanelProps) {
  const { t } = useTranslation()
  const id = useId()
  const [searchParams, setSearchParams] = useSearchParams()
  const priority = oneOf(PRIORITY_CODES, searchParams.get("priority"))
  const status = oneOf(ACTIVE_STATUS_CODES, searchParams.get("status"))
  const incidents = useIncidents({
    active: true,
    priority: priority ? [priority] : undefined,
    status: status ? [status] : undefined,
    sort: "priority",
    limit: LIMIT,
  })

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
        <Link to="/incidents" className={buttonVariants({ variant: "ghost", size: "sm" })}>
          {t("commandCenter.incidents.viewAll")}
        </Link>
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
      className={className}
    >
      <div className="mb-2 flex flex-wrap gap-2">
        <FilterSelect
          id={`${id}-priority`}
          label={t("incidents.filters.priority")}
          value={priority ?? ""}
          onChange={(value) => {
            setFilter("priority", value)
          }}
          options={PRIORITY_CODES.map((code) => ({ value: code, label: t(`priority.${code}`) }))}
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
        />
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("incidents.list.columns.priority")}</TableHead>
            <TableHead>{t("incidents.list.columns.code")}</TableHead>
            <TableHead>{t("incidents.list.columns.title")}</TableHead>
            <TableHead>{t("incidents.list.columns.status")}</TableHead>
            <TableHead>{t("incidents.list.columns.municipality")}</TableHead>
            <TableHead>{t("incidents.list.columns.reportedAt")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {page?.items.map((incident) => {
            const selected = incident.id === selectedId
            return (
              <TableRow key={incident.id} data-state={selected ? "selected" : undefined}>
                <TableCell>
                  <PriorityBadge priority={incident.priority} pulse />
                </TableCell>
                <TableCell>
                  {/* Selecciona sin salir del centro de mando: el resumen va al panel lateral. */}
                  <button
                    type="button"
                    aria-pressed={selected}
                    aria-label={t("commandCenter.incidents.select", { code: incident.code })}
                    onClick={() => {
                      onSelect(incident.id)
                    }}
                    className="rounded-sm font-data font-medium underline-offset-4 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50"
                  >
                    {incident.code}
                  </button>
                </TableCell>
                <TableCell className="max-w-60">
                  <div className="flex min-w-0 items-center gap-1.5">
                    {incident.parent_incident_id && (
                      <FolderTree
                        aria-label={t("incidents.list.child")}
                        className="size-3.5 shrink-0 text-muted-foreground"
                      />
                    )}
                    <span className="truncate">{incident.title}</span>
                    {incident.is_simulated && <SimulatedPill />}
                  </div>
                </TableCell>
                <TableCell>
                  <IncidentStatusPill status={incident.status} />
                </TableCell>
                <TableCell>{incident.location.municipality}</TableCell>
                <TableCell className="font-data text-muted-foreground">
                  <time dateTime={incident.reported_at}>
                    {formatDateTime(incident.reported_at)}
                  </time>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </Panel>
  )
}
