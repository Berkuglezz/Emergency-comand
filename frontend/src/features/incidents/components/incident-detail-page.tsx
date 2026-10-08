import { useQueryClient } from "@tanstack/react-query"
import { FolderTree, Lock, Pencil } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useLocation, useParams } from "react-router"

import { BackLink } from "@/components/ops/back-link"
import { DateTimeText, DetailItem } from "@/components/ops/detail-item"
import { MutationErrorAlert } from "@/components/ops/mutation-error-alert"
import { Panel } from "@/components/ops/panel"
import { PriorityBadge } from "@/components/ops/priority-badge"
import { SimulatedPill } from "@/components/ops/simulated-pill"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { hasPermission, useSession } from "@/features/auth/hooks"
import { ApiError } from "@/lib/api-client"
import { formatNumber } from "@/lib/format"
import { returnState } from "@/lib/navigation"
import { queryKeys } from "@/lib/query-keys"
import { useCodeLabel } from "@/lib/code-label"

import { formValuesFromIncident, toUpdatePayload } from "../form"
import { useIncident, useIncidentTypes, useUpdateIncident } from "../hooks"
import { incidentErrorMessage } from "../presentation"
import type { IncidentDetail, IncidentRef, IncidentType } from "../types"
import { IncidentStatusPill, IncidentTypeLabel } from "./incident-badges"
import { IncidentForm } from "./incident-form"
import { IncidentStatusActions } from "./incident-status-actions"
import { IncidentTimeline } from "./incident-timeline"

/** Detalle de un incidente: resumen, acciones, relación padre/hijos e historial. */
export function IncidentDetailPage() {
  const { t } = useTranslation()
  const { incidentId = "" } = useParams()
  const queryClient = useQueryClient()
  const { data: user } = useSession()
  const incident = useIncident(incidentId)
  const types = useIncidentTypes()

  // Recarga el incidente y su historial (p. ej. tras un 409 `version_conflict`).
  const reload = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.incident(incidentId) })
  }

  if (incident.isPending || incident.isError) {
    const notFound =
      incident.error instanceof ApiError && [404, 422].includes(incident.error.status)
    return (
      <div className="flex flex-col gap-3">
        <BackLink fallback="/incidents" />
        <Panel
          title={t("incidents.detail.summary")}
          status={incident.isPending ? "loading" : "error"}
          error={{
            description: notFound
              ? t("incidents.detail.notFound")
              : incidentErrorMessage(incident.error, t),
            onRetry: notFound ? undefined : () => void incident.refetch(),
          }}
        />
      </div>
    )
  }

  const data = incident.data
  const canUpdate = hasPermission(user, "incidents:update")
  const type = types.data?.find((candidate) => candidate.id === data.type.id)

  return (
    <div className="flex flex-col gap-3">
      <BackLink fallback="/incidents" />
      <IncidentHeader incident={data} />

      <div className="grid min-h-0 gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(320px,400px)]">
        <div className="flex min-w-0 flex-col gap-3">
          {data.closed_at !== null && (
            <Alert>
              <Lock aria-hidden />
              <AlertDescription>{t("incidents.detail.closedNotice")}</AlertDescription>
            </Alert>
          )}
          {canUpdate && (
            <IncidentStatusActions
              incident={data}
              canClose={hasPermission(user, "incidents:close")}
              onReload={reload}
            />
          )}
          <SummaryOrEdit
            incident={data}
            type={type}
            types={types.data ?? []}
            canEdit={canUpdate && data.closed_at === null}
            onReload={reload}
          />
          <Hierarchy incident={data} />
        </div>
        <IncidentTimeline
          incidentId={data.id}
          canAddNotes={canUpdate}
          className="lg:max-h-[80dvh]"
        />
      </div>
    </div>
  )
}

function IncidentHeader({ incident }: { incident: IncidentDetail }) {
  return (
    <header className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-data text-base font-semibold">{incident.code}</span>
        <PriorityBadge
          priority={incident.priority}
          // Pulso solo mientras el incidente crítico sigue activo.
          pulse={incident.closed_at === null}
        />
        <IncidentStatusPill status={incident.status} />
        {incident.is_simulated && <SimulatedPill />}
      </div>
      <h1 className="text-lg font-semibold">{incident.title}</h1>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground">
        <IncidentTypeLabel type={incident.type} />
        <span>{incident.location.municipality}</span>
      </div>
    </header>
  )
}

function SummaryOrEdit({
  incident,
  type,
  types,
  canEdit,
  onReload,
}: {
  incident: IncidentDetail
  type: IncidentType | undefined
  types: IncidentType[]
  canEdit: boolean
  onReload: () => void
}) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const update = useUpdateIncident(incident.id)

  if (editing && canEdit) {
    return (
      <Panel title={t("incidents.detail.editTitle")}>
        <IncidentForm
          // Tras recargar una versión nueva, el formulario se reinicia con sus datos.
          key={incident.version}
          mode="edit"
          types={types}
          defaultValues={formValuesFromIncident(incident)}
          incidentId={incident.id}
          hasChildren={incident.children.length > 0}
          pending={update.isPending}
          submitLabel={t("common.save")}
          pendingLabel={t("common.saving")}
          error={
            update.isError && (
              <MutationErrorAlert
                error={update.error}
                message={incidentErrorMessage(update.error, t)}
                conflict={{
                  title: t("incidents.detail.conflict.title"),
                  description: t("incidents.detail.conflict.description"),
                }}
                onReload={() => {
                  update.reset()
                  onReload()
                }}
              />
            )
          }
          onSubmit={(values) => {
            const payload = toUpdatePayload(values, incident, type?.details_schema_key)
            // Sin cambios reales no se llama a la API (no habría evento ni versión nueva).
            if (!payload) {
              setEditing(false)
              return
            }
            update.mutate(payload, {
              onSuccess: () => {
                setEditing(false)
              },
            })
          }}
          onCancel={() => {
            update.reset()
            setEditing(false)
          }}
        />
      </Panel>
    )
  }

  return (
    <Panel
      title={t("incidents.detail.summary")}
      actions={
        canEdit && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setEditing(true)
            }}
          >
            <Pencil data-icon="inline-start" aria-hidden />
            {t("common.edit")}
          </Button>
        )
      }
    >
      <Summary incident={incident} type={type} />
    </Panel>
  )
}

function Summary({ incident, type }: { incident: IncidentDetail; type: IncidentType | undefined }) {
  const { t } = useTranslation()
  const label = useCodeLabel()
  const hectares = incident.details.affected_hectares
  const vegetation = incident.details.vegetation
  const waterLevel = incident.details.water_level_cm

  return (
    <div className="flex flex-col gap-4">
      <dl className="grid gap-x-4 gap-y-2 sm:grid-cols-2 xl:grid-cols-3">
        <DetailItem label={t("incidents.fields.category")}>
          {type ? label("incidentCategories", type.category) : "—"}
        </DetailItem>
        <DetailItem label={t("incidents.fields.municipality")}>
          {incident.location.municipality}
        </DetailItem>
        <DetailItem label={t("incidents.fields.locationDescription")}>
          {incident.location.description ?? "—"}
        </DetailItem>
        <DetailItem label={t("incidents.fields.affectedPeople")}>
          {incident.affected_people === null ? "—" : formatNumber(incident.affected_people)}
        </DetailItem>
        <DetailItem label={t("incidents.fields.reportedAt")}>
          <DateTimeText value={incident.reported_at} />
        </DetailItem>
        <DetailItem label={t("incidents.fields.updatedAt")}>
          <DateTimeText value={incident.updated_at} />
        </DetailItem>
        {incident.closed_at && (
          <DetailItem label={t("incidents.fields.closedAt")}>
            <DateTimeText value={incident.closed_at} />
          </DetailItem>
        )}
        {/* Datos específicos del tipo: secciones fijas, no campos dinámicos. */}
        {(typeof hectares === "string" || typeof hectares === "number") && (
          <DetailItem label={t("incidentDetails.affected_hectares")}>
            <span className="font-data">{String(hectares)}</span>
          </DetailItem>
        )}
        {(vegetation === "forest" || vegetation === "scrub" || vegetation === "agricultural") && (
          <DetailItem label={t("incidentDetails.vegetation")}>
            {t(`incidentDetails.vegetationValues.${vegetation}`)}
          </DetailItem>
        )}
        {typeof waterLevel === "number" && (
          <DetailItem label={t("incidentDetails.water_level_cm")}>
            <span className="font-data">{formatNumber(waterLevel)}</span>
          </DetailItem>
        )}
      </dl>

      {incident.description && (
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-muted-foreground">
            {t("incidents.fields.description")}
          </span>
          <p className="whitespace-pre-line">{incident.description}</p>
        </div>
      )}

      {type && type.common_risks.length > 0 && (
        <CodeList
          title={t("incidents.fields.risks")}
          items={type.common_risks.map((code) => label("incidentRisks", code))}
        />
      )}
      {type && type.suggested_resource_types.length > 0 && (
        <CodeList
          title={t("incidents.fields.suggestedResources")}
          items={type.suggested_resource_types.map((code) => label("resourceTypes", code))}
        />
      )}
    </div>
  )
}

function Hierarchy({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation()
  if (!incident.parent && incident.children.length === 0) return null

  return (
    <Panel title={t("incidents.detail.hierarchy")}>
      <div className="flex flex-col gap-3">
        {incident.parent && (
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-muted-foreground">
              {t("incidents.fields.parent")}
            </span>
            <RefRow incident={incident.parent} />
          </div>
        )}
        {incident.children.length > 0 && (
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-muted-foreground">
              {t("incidents.fields.children")}
            </span>
            <ul className="flex flex-col gap-1">
              {incident.children.map((child) => (
                <li key={child.id}>
                  <RefRow incident={child} />
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Panel>
  )
}

function RefRow({ incident }: { incident: IncidentRef }) {
  const back = returnState(useLocation())
  return (
    <div className="flex min-h-row flex-wrap items-center gap-2">
      <FolderTree aria-hidden className="size-4 text-muted-foreground" />
      <Link
        to={`/incidents/${incident.id}`}
        state={back}
        className="font-data font-medium underline-offset-4 hover:underline"
      >
        {incident.code}
      </Link>
      <span className="min-w-0 truncate">{incident.title}</span>
      <PriorityBadge priority={incident.priority} />
      <IncidentStatusPill status={incident.status} />
    </div>
  )
}

function CodeList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">{title}</span>
      <ul className="flex flex-wrap gap-1">
        {items.map((item) => (
          <li key={item}>
            <Badge variant="outline" className="rounded-sm">
              {item}
            </Badge>
          </li>
        ))}
      </ul>
    </div>
  )
}
