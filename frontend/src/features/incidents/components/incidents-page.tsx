import { FolderTree, Plus, Search, Siren, X } from "lucide-react"
import { type SubmitEvent, useId } from "react"
import { useTranslation } from "react-i18next"
import { Link, useLocation, useSearchParams } from "react-router"

import { FilterSelect } from "@/components/ops/filter-select"
import { Pagination } from "@/components/ops/pagination"
import { Panel, type PanelStatus } from "@/components/ops/panel"
import { PRIORITY_CODES } from "@/components/ops/priority"
import { PriorityBadge } from "@/components/ops/priority-badge"
import { SimulatedPill } from "@/components/ops/simulated-pill"
import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useCodeLabel } from "@/lib/code-label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { hasPermission, useSession } from "@/features/auth/hooks"
import { formatDateTime, formatNumber } from "@/lib/format"
import { returnState } from "@/lib/navigation"

import {
  COORDINATE_FILTERS,
  type CoordinateFilter,
  hasActiveFilters,
  type IncidentFilters,
  PAGE_SIZE,
  parseFilters,
  serializeFilters,
  SORT_OPTIONS,
  toListParams,
} from "../filters"
import { useIncidents, useIncidentTypes } from "../hooks"
import { incidentErrorMessage, STATUS_CODES } from "../presentation"
import type { IncidentPriority, IncidentSort, IncidentStatus, IncidentSummary } from "../types"
import { IncidentStatusPill, IncidentTypeLabel } from "./incident-badges"
import { UnlocatedMark } from "./unlocated-mark"

/** Listado de incidentes con filtros, orden y paginación guardados en la URL. */
export function IncidentsPage() {
  const { t } = useTranslation()
  const { data: user } = useSession()
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = parseFilters(searchParams)
  const incidents = useIncidents(toListParams(filters))

  // Cualquier cambio de filtro vuelve a la primera página.
  const update = (changes: Partial<IncidentFilters>) => {
    setSearchParams(serializeFilters({ ...filters, page: 1, ...changes }))
  }

  let status: PanelStatus = "ready"
  if (incidents.isPending) status = "loading"
  else if (incidents.isError) status = "error"
  else if (incidents.data.items.length === 0) status = "empty"

  const page = incidents.data
  const from = page && page.total > 0 ? page.offset + 1 : 0
  const to = page ? page.offset + page.items.length : 0

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-col">
          <h1 className="text-lg font-semibold">{t("incidents.title")}</h1>
          <p className="text-muted-foreground">{t("incidents.description")}</p>
        </div>
        {hasPermission(user, "incidents:create") && (
          <Link to="/incidents/new" className={buttonVariants()}>
            <Plus data-icon="inline-start" aria-hidden />
            {t("incidents.new")}
          </Link>
        )}
      </header>

      <FilterBar filters={filters} onChange={update} />

      <Panel
        title={t("incidents.title")}
        description={
          page && page.total > 0
            ? t("incidents.list.range", {
                from: formatNumber(from),
                to: formatNumber(to),
                total: formatNumber(page.total),
              })
            : undefined
        }
        status={status}
        empty={{
          icon: Siren,
          description: hasActiveFilters(filters)
            ? t("incidents.list.emptyFiltered")
            : t("incidents.list.empty"),
        }}
        error={{
          description: incidentErrorMessage(incidents.error, t),
          onRetry: () => void incidents.refetch(),
        }}
        className="min-h-0 flex-1"
      >
        <IncidentTable items={page?.items ?? []} />
        {page && page.total > PAGE_SIZE && (
          <Pagination
            page={filters.page}
            pages={Math.ceil(page.total / PAGE_SIZE)}
            onChange={(next) => {
              setSearchParams(serializeFilters({ ...filters, page: next }))
            }}
          />
        )}
      </Panel>
    </div>
  )
}

function IncidentTable({ items }: { items: IncidentSummary[] }) {
  const { t } = useTranslation()
  // El detalle sabe volver a este listado con sus filtros y página.
  const back = returnState(useLocation())
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("incidents.list.columns.code")}</TableHead>
          <TableHead>{t("incidents.list.columns.priority")}</TableHead>
          <TableHead>{t("incidents.list.columns.status")}</TableHead>
          <TableHead>{t("incidents.list.columns.title")}</TableHead>
          <TableHead>{t("incidents.list.columns.type")}</TableHead>
          <TableHead>{t("incidents.list.columns.municipality")}</TableHead>
          <TableHead>{t("incidents.list.columns.reportedAt")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((incident) => (
          <TableRow key={incident.id}>
            <TableCell>
              <Link
                to={`/incidents/${incident.id}`}
                state={back}
                className="font-data font-medium underline-offset-4 hover:underline focus-visible:underline"
              >
                {incident.code}
              </Link>
            </TableCell>
            <TableCell>
              <PriorityBadge priority={incident.priority} />
            </TableCell>
            <TableCell>
              <IncidentStatusPill status={incident.status} />
            </TableCell>
            <TableCell className="max-w-96">
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
              <IncidentTypeLabel type={incident.type} />
            </TableCell>
            <TableCell>
              <span className="flex items-center gap-1.5">
                {incident.location.municipality}
                {incident.location.latitude === null && <UnlocatedMark />}
              </span>
            </TableCell>
            <TableCell className="font-data text-muted-foreground">
              <time dateTime={incident.reported_at}>{formatDateTime(incident.reported_at)}</time>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function FilterBar({
  filters,
  onChange,
}: {
  filters: IncidentFilters
  onChange: (changes: Partial<IncidentFilters>) => void
}) {
  const { t } = useTranslation()
  const label = useCodeLabel()
  const types = useIncidentTypes()
  const id = useId()

  // La búsqueda de texto se aplica al enviar (Intro o botón), no en cada tecla.
  const onSearch = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()
    const value = new FormData(event.currentTarget).get("q")
    onChange({ q: typeof value === "string" ? value.trim() : "" })
  }

  return (
    <section
      aria-label={t("incidents.filters.label")}
      className="flex flex-wrap items-end gap-2 rounded-lg border bg-card p-2"
    >
      <form role="search" onSubmit={onSearch} className="flex items-end gap-1">
        <div className="flex flex-col gap-1">
          <Label htmlFor={`${id}-q`} className="text-xs text-muted-foreground">
            {t("incidents.filters.search")}
          </Label>
          <Input
            // Al cambiar la URL (p. ej. «Limpiar»), el campo se reinicia con su valor.
            key={filters.q}
            id={`${id}-q`}
            name="q"
            type="search"
            maxLength={100}
            defaultValue={filters.q}
            placeholder={t("incidents.filters.searchPlaceholder")}
            className="w-56"
          />
        </div>
        <Button
          type="submit"
          variant="outline"
          size="icon"
          aria-label={t("incidents.filters.apply")}
        >
          <Search aria-hidden />
        </Button>
      </form>

      <FilterSelect
        id={`${id}-status`}
        label={t("incidents.filters.status")}
        value={filters.status ?? ""}
        onChange={(value) => {
          onChange({ status: (value || null) as IncidentStatus | null })
        }}
        options={STATUS_CODES.map((code) => ({ value: code, label: t(`incidentStatus.${code}`) }))}
      />
      <FilterSelect
        id={`${id}-priority`}
        label={t("incidents.filters.priority")}
        value={filters.priority ?? ""}
        onChange={(value) => {
          onChange({ priority: (value || null) as IncidentPriority | null })
        }}
        options={PRIORITY_CODES.map((code) => ({ value: code, label: t(`priority.${code}`) }))}
      />
      <FilterSelect
        id={`${id}-type`}
        label={t("incidents.filters.type")}
        value={filters.type ?? ""}
        onChange={(value) => {
          onChange({ type: value || null })
        }}
        options={(types.data ?? []).map((type) => ({
          value: type.code,
          label: label("incidentTypes", type.code),
        }))}
      />
      <FilterSelect
        id={`${id}-coords`}
        label={t("incidents.filters.coords")}
        value={filters.coords ?? ""}
        onChange={(value) => {
          onChange({ coords: (value || null) as CoordinateFilter | null })
        }}
        options={COORDINATE_FILTERS.map((code) => ({
          value: code,
          label: t(`incidents.filters.coordsValues.${code}`),
        }))}
      />
      <FilterSelect
        id={`${id}-sort`}
        label={t("incidents.filters.sort")}
        value={filters.sort}
        includeAny={false}
        onChange={(value) => {
          onChange({ sort: value as IncidentSort })
        }}
        options={(Object.keys(SORT_OPTIONS) as (keyof typeof SORT_OPTIONS)[]).map((key) => ({
          value: SORT_OPTIONS[key],
          label: t(`incidents.sort.${key}`),
        }))}
      />

      <label className="flex h-8 items-center gap-2 px-1">
        <input
          type="checkbox"
          className="size-4 accent-primary"
          checked={filters.includeClosed}
          onChange={(event) => {
            onChange({ includeClosed: event.target.checked })
          }}
        />
        {t("incidents.filters.includeClosed")}
      </label>

      {hasActiveFilters(filters) && (
        <Button
          variant="ghost"
          onClick={() => {
            onChange({ q: "", status: null, priority: null, type: null, includeClosed: false })
          }}
        >
          <X data-icon="inline-start" aria-hidden />
          {t("incidents.filters.clear")}
        </Button>
      )}
    </section>
  )
}
