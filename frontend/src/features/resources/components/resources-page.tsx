import { Plus, Search, Truck, X } from "lucide-react"
import { type SubmitEvent, useId } from "react"
import { useTranslation } from "react-i18next"
import { Link, useLocation, useSearchParams } from "react-router"

import { FilterSelect } from "@/components/ops/filter-select"
import { Pagination } from "@/components/ops/pagination"
import { Panel, type PanelStatus } from "@/components/ops/panel"
import { SimulatedPill } from "@/components/ops/simulated-pill"
import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { hasPermission, useSession } from "@/features/auth/hooks"
import { useOrganizations } from "@/features/organizations/hooks"
import { useCodeLabel } from "@/lib/code-label"
import { formatDateTime, formatNumber } from "@/lib/format"
import { returnState } from "@/lib/navigation"

import {
  hasActiveFilters,
  PAGE_SIZE,
  parseFilters,
  type ResourceFilters,
  serializeFilters,
  SORT_OPTIONS,
  toListParams,
} from "../filters"
import { useResources, useResourceTypes } from "../hooks"
import { RESOURCE_STATUS_CODES, resourceErrorMessage } from "../presentation"
import type { Resource, ResourceSort, ResourceStatus } from "../types"
import { DeactivatedPill, ResourceStatusPill, ResourceTypeLabel } from "./resource-badges"

/** Listado de recursos con filtros, orden y paginación guardados en la URL. */
export function ResourcesPage() {
  const { t } = useTranslation()
  const { data: user } = useSession()
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = parseFilters(searchParams)
  const resources = useResources(toListParams(filters))

  const update = (changes: Partial<ResourceFilters>) => {
    setSearchParams(serializeFilters({ ...filters, page: 1, ...changes }))
  }

  let status: PanelStatus = "ready"
  if (resources.isPending) status = "loading"
  else if (resources.isError) status = "error"
  else if (resources.data.items.length === 0) status = "empty"

  const page = resources.data
  const from = page && page.total > 0 ? page.offset + 1 : 0
  const to = page ? page.offset + page.items.length : 0

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-col">
          <h1 className="text-lg font-semibold">{t("resources.title")}</h1>
          <p className="text-muted-foreground">{t("resources.description")}</p>
        </div>
        {hasPermission(user, "resources:manage") && (
          <Link to="/resources/new" className={buttonVariants()}>
            <Plus data-icon="inline-start" aria-hidden />
            {t("resources.new")}
          </Link>
        )}
      </header>

      <FilterBar
        filters={filters}
        onChange={update}
        canFilterByOrganization={hasPermission(user, "organizations:read")}
      />

      <Panel
        title={t("resources.title")}
        description={
          page && page.total > 0
            ? t("resources.list.range", {
                from: formatNumber(from),
                to: formatNumber(to),
                total: formatNumber(page.total),
              })
            : undefined
        }
        status={status}
        empty={{
          icon: Truck,
          description: hasActiveFilters(filters)
            ? t("resources.list.emptyFiltered")
            : t("resources.list.empty"),
        }}
        error={{
          description: resourceErrorMessage(resources.error, t),
          onRetry: () => void resources.refetch(),
        }}
        className="min-h-0 flex-1"
      >
        <ResourceTable items={page?.items ?? []} />
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

function ResourceTable({ items }: { items: Resource[] }) {
  const { t } = useTranslation()
  // La ficha sabe volver a este listado con sus filtros y página.
  const back = returnState(useLocation())
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t("resources.list.columns.code")}</TableHead>
          <TableHead>{t("resources.list.columns.status")}</TableHead>
          <TableHead>{t("resources.list.columns.name")}</TableHead>
          <TableHead>{t("resources.list.columns.type")}</TableHead>
          <TableHead>{t("resources.list.columns.organization")}</TableHead>
          <TableHead>{t("resources.list.columns.municipality")}</TableHead>
          <TableHead>{t("resources.list.columns.statusChangedAt")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((resource) => (
          <TableRow key={resource.id}>
            <TableCell>
              <Link
                to={`/resources/${resource.id}`}
                state={back}
                className="font-data font-medium underline-offset-4 hover:underline focus-visible:underline"
              >
                {resource.code}
              </Link>
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-1">
                <ResourceStatusPill status={resource.status} />
                {!resource.is_active && <DeactivatedPill />}
              </div>
            </TableCell>
            <TableCell className="max-w-80">
              <div className="flex min-w-0 items-center gap-1.5">
                <span className="truncate">{resource.name}</span>
                {resource.is_simulated && <SimulatedPill />}
              </div>
            </TableCell>
            <TableCell>
              <ResourceTypeLabel type={resource.type} />
            </TableCell>
            <TableCell className="max-w-64 truncate">{resource.organization.name}</TableCell>
            <TableCell>{resource.municipality}</TableCell>
            <TableCell className="font-data text-muted-foreground">
              <time dateTime={resource.status_changed_at}>
                {formatDateTime(resource.status_changed_at)}
              </time>
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
  canFilterByOrganization,
}: {
  filters: ResourceFilters
  onChange: (changes: Partial<ResourceFilters>) => void
  canFilterByOrganization: boolean
}) {
  const { t } = useTranslation()
  const label = useCodeLabel()
  const types = useResourceTypes()
  // Sin `organizations:read` no se pide la lista (el backend respondería 403).
  const organizations = useOrganizations({ enabled: canFilterByOrganization })
  const id = useId()

  const onSearch = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()
    const value = new FormData(event.currentTarget).get("q")
    onChange({ q: typeof value === "string" ? value.trim() : "" })
  }

  return (
    <section
      aria-label={t("resources.filters.label")}
      className="flex flex-wrap items-end gap-2 rounded-lg border bg-card p-2"
    >
      <form role="search" onSubmit={onSearch} className="flex items-end gap-1">
        <div className="flex flex-col gap-1">
          <Label htmlFor={`${id}-q`} className="text-xs text-muted-foreground">
            {t("resources.filters.search")}
          </Label>
          <Input
            key={filters.q}
            id={`${id}-q`}
            name="q"
            type="search"
            maxLength={100}
            defaultValue={filters.q}
            placeholder={t("resources.filters.searchPlaceholder")}
            className="w-56"
          />
        </div>
        <Button
          type="submit"
          variant="outline"
          size="icon"
          aria-label={t("resources.filters.apply")}
        >
          <Search aria-hidden />
        </Button>
      </form>

      <FilterSelect
        id={`${id}-status`}
        label={t("resources.filters.status")}
        value={filters.status ?? ""}
        onChange={(value) => {
          onChange({ status: (value || null) as ResourceStatus | null })
        }}
        options={RESOURCE_STATUS_CODES.map((code) => ({
          value: code,
          label: t(`resourceStatus.${code}`),
        }))}
      />
      <FilterSelect
        id={`${id}-type`}
        label={t("resources.filters.type")}
        value={filters.type ?? ""}
        onChange={(value) => {
          onChange({ type: value || null })
        }}
        options={(types.data ?? []).map((type) => ({
          value: type.code,
          label: label("resourceTypes", type.code),
        }))}
      />
      {canFilterByOrganization && (
        <FilterSelect
          id={`${id}-organization`}
          label={t("resources.filters.organization")}
          value={filters.organization ?? ""}
          className="w-64"
          onChange={(value) => {
            onChange({ organization: value || null })
          }}
          options={(organizations.data ?? []).map((organization) => ({
            value: organization.id,
            label: organization.name,
          }))}
        />
      )}
      <FilterSelect
        id={`${id}-sort`}
        label={t("resources.filters.sort")}
        value={filters.sort}
        includeAny={false}
        onChange={(value) => {
          onChange({ sort: value as ResourceSort })
        }}
        options={(Object.keys(SORT_OPTIONS) as (keyof typeof SORT_OPTIONS)[]).map((key) => ({
          value: SORT_OPTIONS[key],
          label: t(`resources.sort.${key}`),
        }))}
      />

      <label className="flex h-8 items-center gap-2 px-1">
        <input
          type="checkbox"
          className="size-4 accent-primary"
          checked={filters.includeInactive}
          onChange={(event) => {
            onChange({ includeInactive: event.target.checked })
          }}
        />
        {t("resources.filters.includeInactive")}
      </label>

      {hasActiveFilters(filters) && (
        <Button
          variant="ghost"
          onClick={() => {
            onChange({
              q: "",
              status: null,
              type: null,
              organization: null,
              includeInactive: false,
            })
          }}
        >
          <X data-icon="inline-start" aria-hidden />
          {t("resources.filters.clear")}
        </Button>
      )}
    </section>
  )
}
